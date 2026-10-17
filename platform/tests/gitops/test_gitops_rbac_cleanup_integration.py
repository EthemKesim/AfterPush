from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from afterpush_api.models import Application, Deployment, Project
from afterpush_api.services.gitops_rbac_cleanup_dry_run import (
    plan_rbac_cleanup,
)
from afterpush_api.services.gitops_rbac_selection import (
    RBACPublicationTarget,
)


def test_cleanup_protects_all_deployment_states(tmp_path):
    database_url = (
        "postgresql+psycopg://afterpush:afterpush_local_dev"
        "@127.0.0.1:5432/afterpush_test"
    )
    engine = create_engine(database_url)

    project_id = uuid4()
    project = Project(
        id=project_id,
        name=f"cleanup-{uuid4().hex[:12]}",
        repository_url="https://example.com/repo.git",
    )

    targets = {}

    try:
        with Session(engine) as db:
            db.add(project)
            db.flush()

            for status in ("pending", "publishing", "published"):
                application = Application(
                    id=uuid4(),
                    project_id=project_id,
                    name=f"{status}-app",
                    image="example/app",
                    port=3000,
                    replicas=1,
                )
                db.add(application)
                db.flush()

                db.add(
                    Deployment(
                        id=uuid4(),
                        application_id=application.id,
                        environment="dev",
                        image_tag="v1",
                        status=status,
                        revision=1,
                    )
                )

                targets[status] = RBACPublicationTarget(
                    project_id=project_id,
                    application_name=application.name,
                    environment="dev",
                )

            db.commit()

        orphan = RBACPublicationTarget(
            project_id=project_id,
            application_name="orphan-app",
            environment="dev",
        )

        for target in (*targets.values(), orphan):
            directory = (
                tmp_path
                / "gitops/platform/rbac/projects"
                / target.environment
                / str(target.project_id)
                / target.application_name
            )
            directory.mkdir(parents=True)

            (directory / "argocd-rbac.yaml").write_text(
                "kind: Role\n"
            )
            (directory / "deployment-rbac.yaml").write_text(
                "kind: RoleBinding\n"
            )

        with Session(engine) as db:
            result = plan_rbac_cleanup(
                db=db,
                repository_root=tmp_path,
                batch_size=2,
            )

        orphaned = {
            candidate.target
            for candidate in result.orphaned_candidates
        }

        assert orphan in orphaned
        assert not orphaned.intersection(targets.values())

    finally:
        with Session(engine) as db:
            db.query(Deployment).filter(
                Deployment.application_id.in_(
                    db.query(Application.id).filter(
                        Application.project_id == project_id
                    )
                )
            ).delete(synchronize_session=False)

            db.query(Application).filter(
                Application.project_id == project_id
            ).delete(synchronize_session=False)

            db.query(Project).filter(
                Project.id == project_id
            ).delete(synchronize_session=False)

            db.commit()

        engine.dispose()
