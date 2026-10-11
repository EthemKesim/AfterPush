
import uuid


def create_project(client):
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "ecommerce-platform",
            "repository_url": "https://github.com/example/ecommerce",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def application_payload(name="orders-api"):
    return {
        "name": name,
        "image": "nginx:1.27",
        "port": 80,
        "replicas": 2,
    }


def create_application(client, project_id, name="orders-api"):
    response = client.post(
        f"/api/v1/projects/{project_id}/applications",
        json=application_payload(name),
    )
    assert response.status_code == 201
    return response.json()


def test_create_application(client):
    project_id = create_project(client)

    response = client.post(
        f"/api/v1/projects/{project_id}/applications",
        json=application_payload(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["project_id"] == project_id
    assert body["name"] == "orders-api"
    assert body["image"] == "nginx:1.27"
    assert body["port"] == 80
    assert body["replicas"] == 2
    assert "id" in body


def test_duplicate_application_returns_409(client):
    project_id = create_project(client)

    create_application(client, project_id)

    response = client.post(
        f"/api/v1/projects/{project_id}/applications",
        json=application_payload(),
    )

    assert response.status_code == 409


def test_list_applications(client):
    project_id = create_project(client)

    create_application(client, project_id, "orders-api")
    create_application(client, project_id, "payment-api")

    response = client.get(
        f"/api/v1/projects/{project_id}/applications"
    )

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert {item["name"] for item in response.json()} == {
        "orders-api",
        "payment-api",
    }


def test_get_application(client):
    project_id = create_project(client)
    application = create_application(client, project_id)

    response = client.get(
        f"/api/v1/applications/{application['id']}"
    )

    assert response.status_code == 200
    assert response.json()["id"] == application["id"]


def test_update_application(client):
    project_id = create_project(client)
    application = create_application(client, project_id)

    response = client.patch(
        f"/api/v1/applications/{application['id']}",
        json={"replicas": 3},
    )

    assert response.status_code == 200
    assert response.json()["replicas"] == 3
    assert response.json()["image"] == "nginx:1.27"
    assert response.json()["port"] == 80


def test_delete_application(client):
    project_id = create_project(client)
    application = create_application(client, project_id)

    response = client.delete(
        f"/api/v1/applications/{application['id']}"
    )

    assert response.status_code == 204

    get_response = client.get(
        f"/api/v1/applications/{application['id']}"
    )
    assert get_response.status_code == 404


def test_create_application_without_project_returns_404(client):
    response = client.post(
        f"/api/v1/projects/{uuid.uuid4()}/applications",
        json=application_payload(),
    )

    assert response.status_code == 404


def test_invalid_application_port_returns_422(client):
    project_id = create_project(client)
    payload = application_payload()
    payload["port"] = 70000

    response = client.post(
        f"/api/v1/projects/{project_id}/applications",
        json=payload,
    )

    assert response.status_code == 422


def test_update_application_with_null_returns_422(client):
    project_id = create_project(client)
    application = create_application(client, project_id)

    response = client.patch(
        f"/api/v1/applications/{application['id']}",
        json={"image": None},
    )

    assert response.status_code == 422
