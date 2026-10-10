
import uuid


def create_project(client):
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "deployment-test-project",
            "repository_url": "https://github.com/example/deployment-test",
        },
    )

    assert response.status_code == 201
    return response.json()["id"]


def create_application(client):
    project_id = create_project(client)

    response = client.post(
        f"/api/v1/projects/{project_id}/applications",
        json={
            "name": "orders-api",
            "image": "nginx",
            "port": 80,
            "replicas": 2,
        },
    )

    assert response.status_code == 201
    return response.json()["id"]


def create_deployment(client, application_id):
    response = client.post(
        f"/api/v1/applications/{application_id}/deployments",
        json={
            "environment": "dev",
            "image_tag": "v1.0.0",
        },
    )

    assert response.status_code == 201
    return response.json()


def test_create_deployment(client):
    application_id = create_application(client)

    deployment = create_deployment(client, application_id)

    assert deployment["application_id"] == application_id
    assert deployment["environment"] == "dev"
    assert deployment["image_tag"] == "v1.0.0"
    assert deployment["status"] == "pending"
    assert "id" in deployment
    assert "created_at" in deployment


def test_list_deployments(client):
    application_id = create_application(client)

    create_deployment(client, application_id)

    response = client.get(
        f"/api/v1/applications/{application_id}/deployments"
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["image_tag"] == "v1.0.0"


def test_get_deployment(client):
    application_id = create_application(client)

    deployment = create_deployment(client, application_id)

    response = client.get(
        f"/api/v1/deployments/{deployment['id']}"
    )

    assert response.status_code == 200
    assert response.json()["id"] == deployment["id"]


def test_create_deployment_without_application_returns_404(client):
    nonexistent_id = uuid.uuid4()

    response = client.post(
        f"/api/v1/applications/{nonexistent_id}/deployments",
        json={
            "environment": "dev",
            "image_tag": "v1.0.0",
        },
    )

    assert response.status_code == 404


def test_list_deployments_without_application_returns_404(client):
    nonexistent_id = uuid.uuid4()

    response = client.get(
        f"/api/v1/applications/{nonexistent_id}/deployments"
    )

    assert response.status_code == 404


def test_get_nonexistent_deployment_returns_404(client):
    nonexistent_id = uuid.uuid4()

    response = client.get(
        f"/api/v1/deployments/{nonexistent_id}"
    )

    assert response.status_code == 404


def test_invalid_deployment_environment_returns_422(client):
    application_id = create_application(client)

    response = client.post(
        f"/api/v1/applications/{application_id}/deployments",
        json={
            "environment": "production123",
            "image_tag": "v1.0.0",
        },
    )

    assert response.status_code == 422


def test_invalid_deployment_image_tag_returns_422(client):
    application_id = create_application(client)

    response = client.post(
        f"/api/v1/applications/{application_id}/deployments",
        json={
            "environment": "dev",
            "image_tag": "invalid tag!",
        },
    )

    assert response.status_code == 422


def test_multiple_deployments_for_same_application(client):
    application_id = create_application(client)

    create_deployment(client, application_id)

    second_response = client.post(
        f"/api/v1/applications/{application_id}/deployments",
        json={
            "environment": "staging",
            "image_tag": "v1.1.0",
        },
    )

    assert second_response.status_code == 201

    response = client.get(
        f"/api/v1/applications/{application_id}/deployments"
    )

    assert response.status_code == 200
    assert len(response.json()) == 2

    environments = {
        deployment["environment"]
        for deployment in response.json()
    }

    assert environments == {"dev", "staging"}


def test_cannot_delete_application_with_deployment_history(client):
    application_id = create_application(client)

    create_deployment(client, application_id)

    response = client.delete(
        f"/api/v1/applications/{application_id}"
    )

    assert response.status_code == 409

    # Application and deployment history must remain intact.
    application_response = client.get(
        f"/api/v1/applications/{application_id}"
    )

    assert application_response.status_code == 200
