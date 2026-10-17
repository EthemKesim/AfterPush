from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.deployment_recovery import recover_published_deployment
from afterpush_api.services.gitops_publication_verifier import (
    GitOpsPublicationVerification,
)


def make_deployment(db):
    project = Project(
        name=f"recovery-hardening-{uuid4().hex[:8]}",
        repository_url="https://github.com/example/source",
    )
    db.add(project)
    db.flush()

    application = Application(
        project_id=project.id,
        name="recovery-hardening-api",
        image="example/recovery-api",
        port=3000,
        replicas=2,
    )
    db.add(application)
    db.flush()

    deployment = Deployment(
        application_id=application.id,
        environment="dev",
        image_tag="v1",
        revision=1,
        status="publishing",
        publication_claim_id=uuid4(),
        publication_claimed_at=datetime.now(timezone.utc) - timedelta(minutes=30),
    )
    db.add(deployment)
    db.flush()

    return application, deployment


def verified():
    return GitOpsPublicationVerification(
        matches=True,
        commit_sha="a" * 40,
        observed_revision=1,
    )


def test_recovery_rejects_superseded_revision(db_session):
    application, deployment = make_deployment(db_session)
    deployment_id = deployment.id

    newer = Deployment(
        application_id=application.id,
        environment="dev",
        image_tag="v2",
        revision=2,
        status="pending",
    )
    db_session.add(newer)
    db_session.commit()

    with patch(
        "afterpush_api.services.deployment_recovery.verify_gitops_publication",
        return_value=verified(),
    ):
        result = recover_published_deployment(
            db=db_session,
            deployment_id=deployment_id,
            gitops_repository_url="unused-local-test-repository",
        )

    assert result == "superseded"

    db_session.refresh(deployment)
    assert deployment.status == "publishing"
    assert deployment.publication_claim_id is not None


def test_recovery_completes_latest_verified_revision(db_session):
    _, deployment = make_deployment(db_session)
    deployment_id = deployment.id
    db_session.commit()

    with patch(
        "afterpush_api.services.deployment_recovery.verify_gitops_publication",
        return_value=verified(),
    ):
        result = recover_published_deployment(
            db=db_session,
            deployment_id=deployment_id,
            gitops_repository_url="unused-local-test-repository",
        )

    assert result == "recovered"

    db_session.refresh(deployment)
    assert deployment.status == "published"
    assert deployment.published_commit_sha == "a" * 40



def test_recovery_rejects_claim_changed_during_verification():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from conftest import TEST_DATABASE_URL

    assert TEST_DATABASE_URL.rsplit("/", 1)[-1] == "afterpush_test"

    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)

    project_id = None
    application_id = None

    try:
        with Session(engine) as db:
            application, deployment = make_deployment(db)

            project_id = application.project_id
            application_id = application.id
            deployment_id = deployment.id
            original_claim_id = deployment.publication_claim_id

            db.commit()

        replacement_claim_id = uuid4()

        def change_claim(*, repository_url, spec):
            # Simulate another worker changing the claim
            # while GitOps verification is in progress.
            with Session(engine) as other_db:
                other_deployment = other_db.get(
                    Deployment, deployment_id
                )

                assert other_deployment.publication_claim_id == original_claim_id

                other_deployment.publication_claim_id = replacement_claim_id
                other_db.commit()

            return verified()

        with Session(engine) as recovery_db:
            with patch(
                "afterpush_api.services.deployment_recovery."
                "verify_gitops_publication",
                side_effect=change_claim,
            ):
                result = recover_published_deployment(
                    db=recovery_db,
                    deployment_id=deployment_id,
                    gitops_repository_url="unused-local-test-repository",
                )

            assert result == "claim_changed"

        with Session(engine) as verify_db:
            current = verify_db.get(Deployment, deployment_id)

            assert current.status == "publishing"
            assert current.publication_claim_id == replacement_claim_id
            assert current.published_commit_sha is None

    finally:
        try:
            if application_id is not None:
                from sqlalchemy import delete

                with Session(engine) as cleanup_db:
                    cleanup_db.execute(
                        delete(Deployment).where(
                            Deployment.application_id == application_id
                        )
                    )
                    cleanup_db.execute(
                        delete(Application).where(
                            Application.id == application_id
                        )
                    )
                    cleanup_db.execute(
                        delete(Project).where(
                            Project.id == project_id
                        )
                    )
                    cleanup_db.commit()
        finally:
            engine.dispose()
