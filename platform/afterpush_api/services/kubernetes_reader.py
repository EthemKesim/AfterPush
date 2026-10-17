import json
from typing import Any

from kubernetes import client


ARGOCD_APPLICATION_GROUP = "argoproj.io"
ARGOCD_APPLICATION_VERSION = "v1alpha1"
ARGOCD_APPLICATION_PLURAL = "applications"
ARGOCD_NAMESPACE = "argocd"


class KubernetesReader:
    """
    Read ArgoCD Applications and Kubernetes Deployments.

    API clients are injected to support offline unit tests.
    This class does not create, modify, or delete resources.
    """

    def __init__(
        self,
        *,
        custom_objects_api: client.CustomObjectsApi,
        apps_api: client.AppsV1Api,
    ) -> None:
        self._custom_objects_api = custom_objects_api
        self._apps_api = apps_api

    def read_argocd_application(
        self,
        application_name: str,
    ) -> dict[str, Any]:
        if not isinstance(application_name, str) or not application_name:
            raise ValueError("Invalid ArgoCD Application name")

        application = (
            self._custom_objects_api.get_namespaced_custom_object(
                group=ARGOCD_APPLICATION_GROUP,
                version=ARGOCD_APPLICATION_VERSION,
                namespace=ARGOCD_NAMESPACE,
                plural=ARGOCD_APPLICATION_PLURAL,
                name=application_name,
            )
        )

        if not isinstance(application, dict):
            raise ValueError("Invalid ArgoCD Application response")

        metadata = application.get("metadata")

        if (
            not isinstance(metadata, dict)
            or metadata.get("name") != application_name
            or metadata.get("namespace") != ARGOCD_NAMESPACE
        ):
            raise ValueError("ArgoCD Application identity mismatch")

        return application

    def read_deployment(
        self,
        *,
        namespace: str,
        deployment_name: str,
    ) -> dict[str, Any]:
        if not isinstance(namespace, str) or not namespace:
            raise ValueError("Invalid Kubernetes namespace")

        if not isinstance(deployment_name, str) or not deployment_name:
            raise ValueError("Invalid Kubernetes Deployment name")

        response = self._apps_api.read_namespaced_deployment(
            name=deployment_name,
            namespace=namespace,
            _preload_content=False,
        )

        deployment = json.loads(response.data)

        if not isinstance(deployment, dict):
            raise ValueError("Invalid Kubernetes Deployment response")

        metadata = deployment.get("metadata")

        if (
            not isinstance(metadata, dict)
            or metadata.get("name") != deployment_name
            or metadata.get("namespace") != namespace
        ):
            raise ValueError("Kubernetes Deployment identity mismatch")

        if (
            deployment.get("apiVersion") != "apps/v1"
            or deployment.get("kind") != "Deployment"
        ):
            raise ValueError("Invalid Kubernetes Deployment resource type")

        return deployment
