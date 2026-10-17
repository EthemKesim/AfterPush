"""Kubernetes clients for deployment prerequisite verification."""

from kubernetes import client, config


def create_prerequisites_clients(
    *,
    in_cluster: bool = False,
    kubeconfig_context: str | None = None,
):
    if in_cluster and kubeconfig_context is not None:
        raise ValueError(
            "Kubeconfig context cannot be used in cluster mode."
        )

    configuration = client.Configuration()

    if in_cluster:
        config.load_incluster_config(
            client_configuration=configuration,
        )
    else:
        config.load_kube_config(
            context=kubeconfig_context,
            client_configuration=configuration,
        )

    api_client = client.ApiClient(configuration=configuration)

    return (
        client.CoreV1Api(api_client),
        client.RbacAuthorizationV1Api(api_client),
    )
