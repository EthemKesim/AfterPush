from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from afterpush_api.services.deployment_worker import (
    get_pending_deployment_ids,
    process_pending_deployments,
)


def test_returns_pending_deployment_ids():
    db = MagicMock()

    first_id = uuid4()
    second_id = uuid4()

    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        (first_id,),
        (second_id,),
    ]

    result = get_pending_deployment_ids(db)

    assert result == [first_id, second_id]
    db.query.return_value.filter.return_value.order_by.return_value.limit.assert_called_once_with(
        20
    )


def test_respects_limit():
    db = MagicMock()

    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    result = get_pending_deployment_ids(db, limit=5)

    assert result == []
    db.query.return_value.filter.return_value.order_by.return_value.limit.assert_called_once_with(
        5
    )


@pytest.mark.parametrize("limit", [0, -1, -10])
def test_rejects_invalid_limit(limit):
    db = MagicMock()

    with pytest.raises(
        ValueError,
        match="limit must be greater than zero",
    ):
        get_pending_deployment_ids(db, limit=limit)

    db.query.assert_not_called()


@patch(
    "afterpush_api.services.deployment_worker.apply_deployment"
)
@patch(
    "afterpush_api.services.deployment_worker.get_pending_deployment_ids"
)
def test_processes_pending_deployments(
    mock_get_pending,
    mock_apply,
):
    db = MagicMock()
    gitops_root = Path("/tmp/gitops")

    first_id = uuid4()
    second_id = uuid4()
    third_id = uuid4()

    mock_get_pending.return_value = [
        first_id,
        second_id,
        third_id,
    ]

    mock_apply.side_effect = [
        "applied",
        "skipped",
        "invalid_status",
    ]

    result = process_pending_deployments(
        db=db,
        gitops_root=gitops_root,
        limit=3,
    )

    assert result == {
        "applied": 1,
        "skipped": 1,
        "not_found": 0,
        "invalid_status": 1,
        "errors": 0,
    }

    assert mock_apply.call_count == 3

    mock_get_pending.assert_called_once_with(
        db=db,
        limit=3,
    )


@patch(
    "afterpush_api.services.deployment_worker.apply_deployment"
)
@patch(
    "afterpush_api.services.deployment_worker.get_pending_deployment_ids"
)
def test_continues_after_deployment_error(
    mock_get_pending,
    mock_apply,
):
    db = MagicMock()

    mock_get_pending.return_value = [
        uuid4(),
        uuid4(),
    ]

    mock_apply.side_effect = [
        RuntimeError("GitOps write failed"),
        "applied",
    ]

    result = process_pending_deployments(
        db=db,
        gitops_root=Path("/tmp/gitops"),
    )

    assert result["errors"] == 1
    assert result["applied"] == 1
    assert mock_apply.call_count == 2
    db.rollback.assert_called()


@patch(
    "afterpush_api.services.deployment_worker.apply_deployment"
)
@patch(
    "afterpush_api.services.deployment_worker.get_pending_deployment_ids"
)
def test_empty_pending_queue(
    mock_get_pending,
    mock_apply,
):
    db = MagicMock()
    mock_get_pending.return_value = []

    result = process_pending_deployments(
        db=db,
        gitops_root=Path("/tmp/gitops"),
    )

    assert result == {
        "applied": 0,
        "skipped": 0,
        "not_found": 0,
        "invalid_status": 0,
        "errors": 0,
    }

    mock_apply.assert_not_called()
