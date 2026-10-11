from uuid import uuid4

import yaml

from afterpush_api.services.sync import sync_gitops_application


def test_same_application_name_is_isolated_between_projects(tmp_path):
    project_a = uuid4()
    project_b = uuid4()

    common = {
        "gitops_root": tmp_path,
        "application_name": "backend",
        "environment": "staging",
        "image_repository": "example/backend",
        "port": 3000,
        "replicas": 2,
    }

    path_a = sync_gitops_application(
        **common,
        project_id=project_a,
        image_tag="v1",
    )

    path_b = sync_gitops_application(
        **common,
        project_id=project_b,
        image_tag="v2",
    )

    assert path_a != path_b
    assert project_a.hex != project_b.hex

    assert str(project_a) in path_a.parts
    assert str(project_b) in path_b.parts

    with path_a.open(encoding="utf-8") as file:
        values_a = yaml.safe_load(file)

    with path_b.open(encoding="utf-8") as file:
        values_b = yaml.safe_load(file)

    assert values_a["image"]["tag"] == "v1"
    assert values_b["image"]["tag"] == "v2"
