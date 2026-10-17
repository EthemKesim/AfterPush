import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    repository_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    applications: Mapped[list["Application"]] = relationship(
        back_populates="project",
    )


class Application(Base):
    __tablename__ = "applications"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "name",
            name="uq_application_project_name",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    image: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    port: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    replicas: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    project: Mapped["Project"] = relationship(
        back_populates="applications",
    )

    deployments: Mapped[list["Deployment"]] = relationship(
        back_populates="application",
    )


class Deployment(Base):
    __tablename__ = "deployments"

    __table_args__ = (
        UniqueConstraint(
            "application_id",
            "environment",
            "revision",
            name="uq_deployment_application_environment_revision",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id"),
        nullable=False,
        index=True,
    )

    promotion_source_deployment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("deployments.id"),
        nullable=True,
        index=True,
    )

    environment: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    image_tag: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    image_repository: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    port: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    replicas: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )

    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    publication_claim_id: Mapped[uuid.UUID | None] = mapped_column(
        nullable=True,
    )

    publication_claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    publication_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    publication_retry_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    published_commit_sha: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    runtime_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="unverified",
        server_default="unverified",
    )

    runtime_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    runtime_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    application: Mapped["Application"] = relationship(
        back_populates="deployments",
    )

    promotion_source: Mapped["Deployment | None"] = relationship(
        foreign_keys=[promotion_source_deployment_id],
        remote_side="Deployment.id",
    )
