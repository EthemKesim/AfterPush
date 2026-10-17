
import uuid

from afterpush_api.models import Application, Deployment


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
    assert deployment["image_repository"] == "nginx"
    assert deployment["image_tag"] == "v1.0.0"
    assert deployment["port"] == 80
    assert deployment["replicas"] == 2
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
    assert response.json()[0]["image_repository"] == "nginx"
    assert response.json()[0]["port"] == 80
    assert response.json()[0]["replicas"] == 2
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


def mark_deployment_healthy(db_session, deployment_id):
    deployment = db_session.get(Deployment, uuid.UUID(deployment_id))
    assert deployment is not None
    deployment.status = "published"
    deployment.runtime_status = "healthy"
    deployment.published_commit_sha = "a" * 40
    db_session.commit()


def test_staging_and_production_must_use_promotion(client):
    application_id = create_application(client)

    for environment in ("staging", "prod"):
        response = client.post(
            f"/api/v1/applications/{application_id}/deployments",
            json={"environment": environment, "image_tag": "v1.1.0"},
        )
        assert response.status_code == 422
        assert "promotion endpoint" in response.json()["detail"]


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


def test_revision_increases_for_dev_deployments(client):
    application_id = create_application(client)

    first = create_deployment(
        client, application_id, "dev", "v1.0.0"
    )

    second = create_deployment(
        client, application_id, "dev", "v1.1.0"
    )

    third = create_deployment(
        client, application_id, "dev", "v1.2.0"
    )

    assert [first["revision"], second["revision"], third["revision"]] == [
        1, 2, 3
    ]


def test_promotion_copies_healthy_source_snapshot_and_requires_prod_approval(
    client,
    db_session,
):
    application_id = create_application(client)
    dev = create_deployment(client, application_id, "dev", "v1.0.0")
    mark_deployment_healthy(db_session, dev["id"])

    staging_response = client.post(
        f"/api/v1/deployments/{dev['id']}/promote",
        json={"target_environment": "staging"},
    )
    assert staging_response.status_code == 201
    staging = staging_response.json()
    assert staging["environment"] == "staging"
    assert staging["status"] == "pending"
    assert staging["promotion_source_deployment_id"] == dev["id"]
    assert staging["image_tag"] == "v1.0.0"
    assert staging["image_repository"] == "nginx"
    assert staging["port"] == 80
    assert staging["replicas"] == 2

    application = db_session.get(Application, uuid.UUID(application_id))
    assert application is not None
    application.image = "registry.example/changed-after-dev"
    application.port = 8080
    application.replicas = 4
    db_session.commit()
    mark_deployment_healthy(db_session, staging["id"])

    prod_response = client.post(
        f"/api/v1/deployments/{staging['id']}/promote",
        json={"target_environment": "prod"},
    )
    assert prod_response.status_code == 201
    prod = prod_response.json()
    assert prod["environment"] == "prod"
    assert prod["status"] == "awaiting_approval"
    assert prod["promotion_source_deployment_id"] == staging["id"]
    assert prod["image_tag"] == "v1.0.0"
    assert prod["image_repository"] == "nginx"
    assert prod["port"] == 80
    assert prod["replicas"] == 2
    assert prod["approved_at"] is None

    approval_response = client.post(
        f"/api/v1/deployments/{prod['id']}/approve"
    )
    assert approval_response.status_code == 200
    approved = approval_response.json()
    assert approved["status"] == "pending"
    assert approved["approved_at"] is not None


def test_promotion_rejects_unhealthy_source(client):
    application_id = create_application(client)
    dev = create_deployment(client, application_id)

    response = client.post(
        f"/api/v1/deployments/{dev['id']}/promote",
        json={"target_environment": "staging"},
    )

    assert response.status_code == 409
    assert "healthy runtime status" in response.json()["detail"]


def test_deployment_timeline_returns_promotion_links(client, db_session):
    application_id = create_application(client)
    dev = create_deployment(client, application_id)
    mark_deployment_healthy(db_session, dev["id"])
    staging_response = client.post(
        f"/api/v1/deployments/{dev['id']}/promote",
        json={"target_environment": "staging"},
    )
    assert staging_response.status_code == 201

    response = client.get(
        f"/api/v1/applications/{application_id}/deployment-timeline"
    )

    assert response.status_code == 200
    timeline = response.json()
    assert [deployment["environment"] for deployment in timeline] == [
        "dev",
        "staging",
    ]
    assert timeline[1]["promotion_source_deployment_id"] == dev["id"]


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
