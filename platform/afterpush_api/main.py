
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel
from afterpush_engine.generation import generate_helm_values
from afterpush_engine.validation import (
    load_schema,
    validate_config,
)


app = FastAPI(
    title="AfterPush Platform API",
    description="Self-service deployment platform API",
    version="0.1.0",
)


class ConfigurationRequest(BaseModel):
    config: dict[str, Any]


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "afterpush-platform-api",
    }


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
