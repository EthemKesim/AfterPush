
from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from afterpush_api.database import SessionLocal
from afterpush_api.models import Project
from afterpush_api.schemas import ProjectCreate, ProjectResponse

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
