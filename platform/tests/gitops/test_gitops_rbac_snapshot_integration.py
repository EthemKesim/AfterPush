from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from afterpush_api.database import engine
from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.gitops_rbac_cleanup_snapshot import (
    collect_rbac_targets_snapshot,
)
from afterpush_api.services.gitops_rbac_selection import (
    RBACPublicationTarget,
    collect_all_rbac_publication_targets,
)


def test_snapshot_is_consistent_across_concurrent_insert():
    # Use the dedicated test database, never the development database.
    assert engine.url.database == "afterpush_test", (
        "This integration test requires DATABASE_URL "
        "to point to afterpush_test"
    )

    factory = sessionmaker(bind=engine, autoflush=False)
    project_id = uuid4()
    application_id = uuid4()
    project_name = f"snapshot-integration-{uuid4().hex[:12]}"

    target = RBACPublicationTarget(
        project_id=project_id,
        application_name="snapshot-backend",
        environment="dev",
    )

    try:
        with factory() as snapshot_session:
            with snapshot_session.begin():
                snapshot_session.execute(
                    text(
                        "SET TRANSACTION ISOLATION LEVEL "
                        "REPEATABLE READ, READ ONLY"
                    )
                )

                before = collect_all_rbac_publication_targets(
                    snapshot_session,
                    batch_size=10,
                )

                with factory.begin() as writer:
                    writer.add(
                        Project(
                            id=project_id,
                            name=project_name,
                            repository_url="https://example.com/source",
                        )
                    )
                    writer.flush()

                    writer.add(
                        Application(
                            id=application_id,
                            project_id=project_id,
                            name="snapshot-backend",
                            image="example/backend",
                            port=3000,
                            replicas=1,
                        )
                    )
                    writer.flush()

                    writer.add(
                        Deployment(
                            application_id=application_id,
                            environment="dev",
                            image_tag="v1",
                            status="published",
                            revision=1,
                        )
                    )

                during = collect_all_rbac_publication_targets(
                    snapshot_session,
                    batch_size=10,
                )

                assert target not in before
                assert target not in during

        with factory() as fresh_session:
            after = collect_rbac_targets_snapshot(
                fresh_session,
                batch_size=10,
            )

        assert target in after

    finally:
        # Remove only the records created by this test.
        with factory.begin() as cleanup:
            cleanup.query(Deployment).filter(
                Deployment.application_id == application_id
            ).delete(synchronize_session=False)

            cleanup.query(Application).filter(
                Application.id == application_id
            ).delete(synchronize_session=False)

            cleanup.query(Project).filter(
                Project.id == project_id
            ).delete(synchronize_session=False)
