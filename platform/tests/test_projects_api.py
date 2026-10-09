
import uuid


def project_payload(name="payment-api"):
    return {
        "name": name,
        "repository_url": "https://github.com/example/payment-api",
    }


def test_create_project(client):
    response = client.post(
        "/api/v1/projects",
        json=project_payload(),
    )

    assert response.status_code == 201

    body = response.json()

    assert body["name"] == "payment-api"
    assert body["repository_url"] == (
        "https://github.com/example/payment-api"
    )
    assert "id" in body
    assert "created_at" in body


def test_duplicate_project_returns_409(client):
    payload = project_payload()

    first = client.post("/api/v1/projects", json=payload)
    second = client.post("/api/v1/projects", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"] == (
        "A project with this name already exists"
    )


def test_list_projects(client):
    client.post(
        "/api/v1/projects",
        json=project_payload("orders-api"),
    )

    response = client.get("/api/v1/projects")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "orders-api"


def test_get_project_by_id(client):
    created = client.post(
        "/api/v1/projects",
        json=project_payload(),
    )

    project_id = created.json()["id"]

    response = client.get(f"/api/v1/projects/{project_id}")

    assert response.status_code == 200
    assert response.json()["id"] == project_id
    assert response.json()["name"] == "payment-api"


def test_get_nonexistent_project_returns_404(client):
    missing_id = uuid.uuid4()

    response = client.get(f"/api/v1/projects/{missing_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


def test_invalid_project_name_returns_422(client):
    response = client.post(
        "/api/v1/projects",
        json=project_payload("Invalid Project Name!"),
    )

    assert response.status_code == 422
