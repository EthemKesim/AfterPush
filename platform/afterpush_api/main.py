
from time import perf_counter
from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.requests import Request

from afterpush_api.database import SessionLocal
from afterpush_api.models import Application, Deployment, Project
from afterpush_api.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS,
    metrics_response,
)
from afterpush_api.schemas import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationUpdate,
    DeploymentCreate,
    DeploymentPromotionCreate,
    DeploymentResponse,
    ProjectCreate,
    ProjectResponse,
)
from afterpush_api.services.deployment_revision import (
    DeploymentPromotionNotFound,
    DeploymentPromotionRejected,
    approve_production_promotion,
    create_promoted_deployment,
    create_versioned_deployment,
)
from afterpush_engine.generation import generate_helm_values
from afterpush_engine.validation import (
    load_schema,
    validate_config,
)


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="AfterPush Platform API",
    description="Self-service deployment platform API",
    version="0.1.0",
)


@app.middleware("http")
async def record_http_metrics(request: Request, call_next):
    """Record stable route templates without counting Prometheus scrapes."""
    if request.url.path == "/metrics":
        return await call_next(request)

    started_at = perf_counter()
    status_code = "500"
    route_path = "unmatched"

    try:
        response = await call_next(request)
        status_code = str(response.status_code)
        route = request.scope.get("route")
        route_path = getattr(route, "path", None) or "unmatched"
        return response
    finally:
        elapsed_seconds = perf_counter() - started_at
        HTTP_REQUESTS.labels(
            method=request.method,
            route=route_path,
            status_code=status_code,
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(
            method=request.method,
            route=route_path,
            status_code=status_code,
        ).observe(elapsed_seconds)


# =========================================================
# DATABASE DEPENDENCY
# =========================================================

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# =========================================================
# REQUEST MODELS
# =========================================================

class ConfigurationRequest(BaseModel):
    config: dict[str, Any]


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "afterpush-platform-api",
    }


@app.get("/metrics", include_in_schema=False)
def metrics():
    return metrics_response()


# =========================================================
# CONFIGURATION VALIDATION
# =========================================================

@app.post("/api/v1/configs/validate")
def validate_application(request: ConfigurationRequest):
    schema = load_schema()

    errors = validate_config(
        request.config,
        schema,
    )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
    }


# =========================================================
# HELM VALUES GENERATION
# =========================================================

@app.post("/api/v1/configs/render")
def render_application(request: ConfigurationRequest):
    schema = load_schema()

    errors = validate_config(
        request.config,
        schema,
    )

    if errors:
        return {
            "valid": False,
            "errors": errors,
        }

    values = generate_helm_values(request.config)

    return {
        "valid": True,
        "helm_values": values,
    }


# =========================================================
# PROJECT MANAGEMENT
# =========================================================

@app.post(
    "/api/v1/projects",
    response_model=ProjectResponse,
    status_code=201,
)
def create_project(
    project: ProjectCreate,
    db: Session = Depends(get_db),
):
    new_project = Project(
        name=project.name,
        repository_url=project.repository_url,
    )

    db.add(new_project)

    try:
        db.commit()

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="A project with this name already exists",
        )

    db.refresh(new_project)

    return new_project


@app.get(
    "/api/v1/projects",
    response_model=list[ProjectResponse],
)
def list_projects(
    db: Session = Depends(get_db),
):
    projects = (
        db.query(Project)
        .order_by(Project.created_at.desc())
        .all()
    )

    return projects


@app.get(
    "/api/v1/projects/{project_id}",
    response_model=ProjectResponse,
    responses={
        404: {"description": "Project not found"},
        422: {"description": "Invalid project ID"},
    },
)
def get_project(
    project_id: UUID,
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        )

    return project


# =========================================================
# APPLICATION MANAGEMENT
# =========================================================

@app.post(
    "/api/v1/projects/{project_id}/applications",
    response_model=ApplicationResponse,
    status_code=201,
)
def create_application(
    project_id: UUID,
    application: ApplicationCreate,
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        )

    new_application = Application(
        project_id=project_id,
        name=application.name,
        image=application.image,
        port=application.port,
        replicas=application.replicas,
    )

    db.add(new_application)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An application with this name already exists in this project",
        )

    db.refresh(new_application)

    return new_application


@app.get(
    "/api/v1/projects/{project_id}/applications",
    response_model=list[ApplicationResponse],
)
def list_applications(
    project_id: UUID,
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        )

    applications = (
        db.query(Application)
        .filter(Application.project_id == project_id)
        .order_by(Application.created_at.desc())
        .all()
    )

    return applications


@app.get(
    "/api/v1/applications/{application_id}",
    response_model=ApplicationResponse,
    responses={
        404: {"description": "Application not found"},
        422: {"description": "Invalid application ID"},
    },
)
def get_application(
    application_id: UUID,
    db: Session = Depends(get_db),
):
    application = db.get(Application, application_id)

    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found",
        )

    return application


@app.patch(
    "/api/v1/applications/{application_id}",
    response_model=ApplicationResponse,
    responses={
        404: {"description": "Application not found"},
        422: {"description": "Invalid application data"},
    },
)
def update_application(
    application_id: UUID,
    updates: ApplicationUpdate,
    db: Session = Depends(get_db),
):
    application = db.get(Application, application_id)

    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found",
        )

    update_data = updates.model_dump(exclude_unset=True)

    if any(value is None for value in update_data.values()):
        raise HTTPException(
            status_code=422,
            detail="Application fields cannot be null",
        )

    for field, value in update_data.items():
        setattr(application, field, value)

    db.commit()
    db.refresh(application)

    return application


@app.delete(
    "/api/v1/applications/{application_id}",
    status_code=204,
    responses={
        404: {"description": "Application not found"},
        422: {"description": "Invalid application ID"},
    },
)
def delete_application(
    application_id: UUID,
    db: Session = Depends(get_db),
):
    application = db.get(Application, application_id)

    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found",
        )

    if application.deployments:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete an application with deployment history",
        )

    db.delete(application)
    db.commit()


# =========================================================
# DEPLOYMENT MANAGEMENT
# =========================================================

@app.post(
    "/api/v1/applications/{application_id}/deployments",
    response_model=DeploymentResponse,
    status_code=201,
    responses={
        404: {"description": "Application not found"},
        422: {"description": "Invalid deployment data"},
    },
)
def create_deployment(
    application_id: UUID,
    deployment: DeploymentCreate,
    db: Session = Depends(get_db),
):
    try:
        if deployment.environment != "dev":
            raise HTTPException(
                status_code=422,
                detail=(
                    "Create deployments in dev first. Use the promotion "
                    "endpoint for staging and prod."
                ),
            )

        new_deployment = create_versioned_deployment(
            db=db,
            application_id=application_id,
            environment=deployment.environment,
            image_tag=deployment.image_tag,
        )

        if new_deployment is None:
            raise HTTPException(
                status_code=404,
                detail="Application not found",
            )

        db.commit()
        db.refresh(new_deployment)

        return new_deployment

    except Exception:
        db.rollback()
        raise


@app.post(
    "/api/v1/deployments/{deployment_id}/promote",
    response_model=DeploymentResponse,
    status_code=201,
    responses={
        404: {"description": "Source deployment not found"},
        409: {"description": "Promotion readiness gate rejected"},
    },
)
def promote_deployment(
    deployment_id: UUID,
    promotion: DeploymentPromotionCreate,
    db: Session = Depends(get_db),
):
    try:
        new_deployment = create_promoted_deployment(
            db,
            source_deployment_id=deployment_id,
            target_environment=promotion.target_environment,
        )
        db.commit()
        db.refresh(new_deployment)
        return new_deployment
    except DeploymentPromotionNotFound:
        db.rollback()
        raise HTTPException(status_code=404, detail="Deployment not found")
    except DeploymentPromotionRejected as error:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(error))
    except Exception:
        db.rollback()
        raise


@app.post(
    "/api/v1/deployments/{deployment_id}/approve",
    response_model=DeploymentResponse,
    responses={
        404: {"description": "Deployment not found"},
        409: {"description": "Production approval rejected"},
    },
)
def approve_deployment(
    deployment_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        deployment = approve_production_promotion(
            db,
            deployment_id=deployment_id,
        )
        db.commit()
        db.refresh(deployment)
        return deployment
    except DeploymentPromotionNotFound:
        db.rollback()
        raise HTTPException(status_code=404, detail="Deployment not found")
    except DeploymentPromotionRejected as error:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(error))
    except Exception:
        db.rollback()
        raise


@app.get(
    "/api/v1/applications/{application_id}/deployments",
    response_model=list[DeploymentResponse],
    responses={
        404: {"description": "Application not found"},
        422: {"description": "Invalid application ID"},
    },
)
def list_deployments(
    application_id: UUID,
    db: Session = Depends(get_db),
):
    application = db.get(Application, application_id)

    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found",
        )

    deployments = (
        db.query(Deployment)
        .filter(Deployment.application_id == application_id)
        .order_by(
            Deployment.created_at.desc(),
            Deployment.id.desc(),
        )
        .all()
    )

    return deployments


@app.get(
    "/api/v1/applications/{application_id}/deployment-timeline",
    response_model=list[DeploymentResponse],
    responses={404: {"description": "Application not found"}},
)
def get_deployment_timeline(
    application_id: UUID,
    db: Session = Depends(get_db),
):
    """Return chronological deployment history and promotion links."""
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    deployments = (
        db.query(Deployment)
        .filter(Deployment.application_id == application_id)
        .order_by(Deployment.created_at.asc(), Deployment.id.asc())
        .all()
    )

    # Database timestamps may have the same resolution for a source and its
    # immediate promotion. Preserve chronology while ensuring a source is
    # always displayed before the deployment that copied it.
    ordered: list[Deployment] = []
    remaining = list(deployments)
    ordered_ids = set()
    while remaining:
        ready = [
            deployment
            for deployment in remaining
            if (
                deployment.promotion_source_deployment_id is None
                or deployment.promotion_source_deployment_id in ordered_ids
            )
        ]
        if not ready:
            # A historical broken link should not make the timeline unusable.
            ready = [remaining[0]]

        for deployment in ready:
            ordered.append(deployment)
            ordered_ids.add(deployment.id)
            remaining.remove(deployment)

    return ordered


@app.get(
    "/api/v1/deployments/{deployment_id}",
    response_model=DeploymentResponse,
    responses={
        404: {"description": "Deployment not found"},
        422: {"description": "Invalid deployment ID"},
    },
)
def get_deployment(
    deployment_id: UUID,
    db: Session = Depends(get_db),
):
    deployment = db.get(Deployment, deployment_id)

    if deployment is None:
        raise HTTPException(
            status_code=404,
            detail="Deployment not found",
        )

    return deployment
