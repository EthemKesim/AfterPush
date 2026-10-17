
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(
        min_length=3,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )

    repository_url: str = Field(
        min_length=1,
        max_length=500,
    )


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    repository_url: str
    created_at: datetime


class ApplicationCreate(BaseModel):
    name: str = Field(
        min_length=3,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )

    image: str = Field(
        min_length=1,
        max_length=500,
    )

    port: int = Field(
        ge=1,
        le=65535,
    )

    replicas: int = Field(
        default=1,
        ge=1,
        le=20,
    )


class ApplicationUpdate(BaseModel):
    image: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )

    port: int | None = Field(
        default=None,
        ge=1,
        le=65535,
    )

    replicas: int | None = Field(
        default=None,
        ge=1,
        le=20,
    )


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    image: str
    port: int
    replicas: int
    created_at: datetime


class DeploymentCreate(BaseModel):
    environment: Literal["dev", "staging", "prod"]

    image_tag: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$",
    )


class DeploymentPromotionCreate(BaseModel):
    target_environment: Literal["staging", "prod"]


class DeploymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    application_id: UUID
    promotion_source_deployment_id: UUID | None
    environment: str
    image_repository: str
    image_tag: str
    port: int
    replicas: int
    status: str
    revision: int
    created_at: datetime
    runtime_status: str
    runtime_reason: str | None
    runtime_checked_at: datetime | None
    approved_at: datetime | None
