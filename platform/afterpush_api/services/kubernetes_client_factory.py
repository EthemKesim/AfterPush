from kubernetes import client, config

from afterpush_api.services.kubernetes_reader import KubernetesReader


def create_kubernetes_reader(
    *,
    in_cluster: bool = False,
    kubeconfig_context: str | None = None,
) -> KubernetesReader:
    """
    Configure Kubernetes API clients and create a read-only reader.

    Local mode uses kubeconfig.
    In-cluster mode uses the Pod's ServiceAccount credentials.

    Creating the reader does not contact the Kubernetes API.
    """

    if in_cluster:
        if kubeconfig_context is not None:
            raise ValueError(
                "Kubeconfig context cannot be used in cluster mode"
            )

        configuration = client.Configuration()
        config.load_incluster_config(
            client_configuration=configuration,
        )
    else:
        configuration = client.Configuration()
        config.load_kube_config(
            context=kubeconfig_context,
            client_configuration=configuration,
        )

    api_client = client.ApiClient(configuration=configuration)

    return KubernetesReader(
        custom_objects_api=client.CustomObjectsApi(api_client),
        apps_api=client.AppsV1Api(api_client),
    )
