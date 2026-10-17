from unittest.mock import Mock, patch

import pytest

from afterpush_api.services.kubernetes_client_factory import (
    create_kubernetes_reader,
)
from afterpush_api.services.kubernetes_reader import KubernetesReader


MODULE = "afterpush_api.services.kubernetes_client_factory"


@patch(f"{MODULE}.client")
@patch(f"{MODULE}.config")
def test_local_mode_uses_kubeconfig(mock_config, mock_client):
    reader = create_kubernetes_reader(
        kubeconfig_context="afterpush-test",
    )

    assert isinstance(reader, KubernetesReader)

    configuration = mock_client.Configuration.return_value
    api_client = mock_client.ApiClient.return_value

    mock_config.load_kube_config.assert_called_once_with(
        context="afterpush-test",
        client_configuration=configuration,
    )
    mock_config.load_incluster_config.assert_not_called()

    mock_client.ApiClient.assert_called_once_with(
        configuration=configuration,
    )
    mock_client.CustomObjectsApi.assert_called_once_with(api_client)
    mock_client.AppsV1Api.assert_called_once_with(api_client)


@patch(f"{MODULE}.client")
@patch(f"{MODULE}.config")
def test_in_cluster_mode_uses_service_account(mock_config, mock_client):
    reader = create_kubernetes_reader(in_cluster=True)

    assert isinstance(reader, KubernetesReader)

    configuration = mock_client.Configuration.return_value

    mock_config.load_incluster_config.assert_called_once_with(
        client_configuration=configuration,
    )
    mock_config.load_kube_config.assert_not_called()


@patch(f"{MODULE}.client")
@patch(f"{MODULE}.config")
def test_default_mode_uses_kubeconfig(mock_config, mock_client):
    create_kubernetes_reader()

    mock_config.load_kube_config.assert_called_once_with(
        context=None,
        client_configuration=mock_client.Configuration.return_value,
    )
    mock_config.load_incluster_config.assert_not_called()


@patch(f"{MODULE}.client")
@patch(f"{MODULE}.config")
def test_rejects_context_in_cluster_mode(mock_config, mock_client):
    with pytest.raises(
        ValueError,
        match="Kubeconfig context cannot be used in cluster mode",
    ):
        create_kubernetes_reader(
            in_cluster=True,
            kubeconfig_context="afterpush-test",
        )

    mock_config.load_kube_config.assert_not_called()
    mock_config.load_incluster_config.assert_not_called()
    mock_client.ApiClient.assert_not_called()


@patch(f"{MODULE}.client")
@patch(f"{MODULE}.config")
def test_propagates_kubeconfig_error(mock_config, mock_client):
    mock_config.load_kube_config.side_effect = RuntimeError(
        "Kubeconfig unavailable"
    )

    with pytest.raises(RuntimeError, match="Kubeconfig unavailable"):
        create_kubernetes_reader()

    mock_client.ApiClient.assert_not_called()


@patch(f"{MODULE}.client")
@patch(f"{MODULE}.config")
def test_propagates_in_cluster_config_error(mock_config, mock_client):
    mock_config.load_incluster_config.side_effect = RuntimeError(
        "ServiceAccount credentials unavailable"
    )

    with pytest.raises(
        RuntimeError,
        match="ServiceAccount credentials unavailable",
    ):
        create_kubernetes_reader(in_cluster=True)

    mock_client.ApiClient.assert_not_called()


@patch(f"{MODULE}.client")
@patch(f"{MODULE}.config")
def test_creates_separate_api_clients(mock_config, mock_client):
    first_api_client = Mock()
    second_api_client = Mock()

    mock_client.ApiClient.side_effect = [
        first_api_client,
        second_api_client,
    ]

    first_reader = create_kubernetes_reader()
    second_reader = create_kubernetes_reader()

    assert isinstance(first_reader, KubernetesReader)
    assert isinstance(second_reader, KubernetesReader)
    assert first_reader is not second_reader

    assert mock_client.ApiClient.call_count == 2
    assert mock_client.CustomObjectsApi.call_count == 2
    assert mock_client.AppsV1Api.call_count == 2
