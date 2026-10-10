
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


def create_deployment(
    client,
    application_id,
    environment="dev",
    image_tag="v1.0.0",
):
    response = client.post(
        f"/api/v1/applications/{application_id}/deployments",
        json={
            "environment": environment,
            "image_tag": image_tag,
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
    assert deployment["revision"] == 1
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
    assert response.json()[0]["revision"] == 1


def test_get_deployment(client):
    application_id = create_application(client)

    deployment = create_deployment(client, application_id)

    response = client.get(
        f"/api/v1/deployments/{deployment['id']}"
    )

    assert response.status_code == 200
    assert response.json()["id"] == deployment["id"]
    assert response.json()["revision"] == 1


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

    first = create_deployment(client, application_id)

    second = create_deployment(
        client,
        application_id,
        environment="staging",
        image_tag="v1.1.0",
    )

    assert first["revision"] == 1
    assert second["revision"] == 1

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

    application_response = client.get(
        f"/api/v1/applications/{application_id}"
    )

    assert application_response.status_code == 200


def test_revision_increases_for_same_environment(client):
    application_id = create_application(client)

    first = create_deployment(
        client, application_id, "staging", "v1.0.0"
    )

    second = create_deployment(
        client, application_id, "staging", "v1.1.0"
    )

    third = create_deployment(
        client, application_id, "staging", "v1.2.0"
    )

    assert [first["revision"], second["revision"], third["revision"]] == [
        1, 2, 3
    ]


def test_revision_is_independent_per_environment(client):
    application_id = create_application(client)

    staging_first = create_deployment(
        client, application_id, "staging", "v1.0.0"
    )

    staging_second = create_deployment(
        client, application_id, "staging", "v1.1.0"
    )

    production_first = create_deployment(
        client, application_id, "prod", "v1.0.0"
    )

    assert staging_first["revision"] == 1
    assert staging_second["revision"] == 2
    assert production_first["revision"] == 1


def test_revision_is_independent_per_application(client):
    first_application = create_application(client)

    first_deployment = create_deployment(
        client, first_application, "dev", "v1.0.0"
    )

    second_deployment = create_deployment(
        client, first_application, "dev", "v1.1.0"
    )

    assert first_deployment["revision"] == 1
    assert second_deployment["revision"] == 2

    second_project_response = client.post(
        "/api/v1/projects",
        json={
            "name": "second-deployment-project",
            "repository_url": "https://github.com/example/second-project",
        },
    )

    assert second_project_response.status_code == 201
    second_project_id = second_project_response.json()["id"]

    second_application_response = client.post(
        f"/api/v1/projects/{second_project_id}/applications",
        json={
            "name": "billing-api",
            "image": "nginx",
            "port": 8080,
            "replicas": 1,
        },
    )

    assert second_application_response.status_code == 201
    second_application_id = second_application_response.json()["id"]

    other_application_deployment = create_deployment(
        client, second_application_id, "dev", "v1.0.0"
    )

    assert other_application_deployment["revision"] == 1


def test_revision_cannot_be_set_by_client(client):
    application_id = create_application(client)

    response = client.post(
        f"/api/v1/applications/{application_id}/deployments",
        json={
            "environment": "dev",
            "image_tag": "v1.0.0",
            "revision": 999,
        },
    )

    assert response.status_code == 201
    assert response.json()["revision"] == 1
