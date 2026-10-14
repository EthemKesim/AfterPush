import uuid


def create_deployment(client):
    project_response = client.post(
        "/api/v1/projects",
        json={
            "name": "status-test-project",
            "repository_url": "https://github.com/example/status-test",
        },
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    application_response = client.post(
        f"/api/v1/projects/{project_id}/applications",
        json={
            "name": "status-test-api",
            "image": "nginx",
            "port": 80,
            "replicas": 1,
        },
    )
    assert application_response.status_code == 201
    application_id = application_response.json()["id"]

    deployment_response = client.post(
        f"/api/v1/applications/{application_id}/deployments",
        json={
            "environment": "dev",
            "image_tag": "v1.0.0",
        },
    )
    assert deployment_response.status_code == 201

    return deployment_response.json()["id"]


def test_status_patch_is_not_allowed(client):
    deployment_id = create_deployment(client)

    response = client.patch(
        f"/api/v1/deployments/{deployment_id}/status",
        json={"status": "running"},
    )

    assert response.status_code == 404


def test_publication_status_cannot_be_set_by_api(client):
    deployment_id = create_deployment(client)

    for status in ("publishing", "published", "succeeded", "failed"):
        response = client.patch(
            f"/api/v1/deployments/{deployment_id}/status",
            json={"status": status},
        )
        assert response.status_code == 404

    get_response = client.get(
        f"/api/v1/deployments/{deployment_id}"
    )

    assert get_response.status_code == 200
    assert get_response.json()["status"] == "pending"


def test_deployment_status_is_readable(client):
    deployment_id = create_deployment(client)

    response = client.get(
        f"/api/v1/deployments/{deployment_id}"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"


def test_nonexistent_deployment_status_patch_is_not_allowed(client):
    response = client.patch(
        f"/api/v1/deployments/{uuid.uuid4()}/status",
        json={"status": "running"},
    )

    assert response.status_code == 404
