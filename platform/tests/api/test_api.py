
from fastapi.testclient import TestClient

from afterpush_api.main import app


client = TestClient(app)


def valid_config():
    return {
        "apiVersion": "afterpush.dev/v1",
        "kind": "Application",
        "metadata": {
            "name": "demo-api",
        },
        "spec": {
            "profile": "local",
            "image": {
                "repository": "demo-api",
                "tag": "v1",
            },
            "port": 3000,
            "health": {
                "path": "/health",
            },
        },
    }


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_validate_valid_config():
    response = client.post(
        "/api/v1/configs/validate",
        json={"config": valid_config()},
    )

    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "errors": [],
    }


def test_validate_invalid_port():
    config = valid_config()
    config["spec"]["port"] = 70000

    response = client.post(
        "/api/v1/configs/validate",
        json={"config": config},
    )

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert any(
        "spec.port" in error
        for error in response.json()["errors"]
    )


def test_render_valid_config():
    response = client.post(
        "/api/v1/configs/render",
        json={"config": valid_config()},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["valid"] is True
    assert body["helm_values"]["application"]["name"] == "demo-api"
    assert body["helm_values"]["image"]["tag"] == "v1"
    assert body["helm_values"]["service"]["targetPort"] == 3000


def test_render_invalid_config():
    config = valid_config()
    config["spec"]["port"] = 70000

    response = client.post(
        "/api/v1/configs/render",
        json={"config": config},
    )

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert "helm_values" not in response.json()
