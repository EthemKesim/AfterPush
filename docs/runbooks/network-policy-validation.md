# NetworkPolicy Validation Runbook

The AfterPush Helm chart keeps NetworkPolicy disabled by default. A policy
only restricts traffic when the cluster CNI enforces NetworkPolicy, and the
correct ingress source differs between NGINX, an AWS load balancer, and local
clusters.

Before enabling it for an application, confirm three things in a controlled
environment:

1. The cluster network plugin enforces Kubernetes NetworkPolicy resources.
2. The actual ingress and monitoring Pods have stable namespaces.
3. Traffic reaches the application through the configured Service port.

Example values:

```yaml
networkPolicy:
  enabled: true
  allowedIngressNamespaces:
    - ingress-nginx
    - monitoring
```

The rendered policy allows TCP traffic only to `service.targetPort`, from Pods
in the same project namespace and from the selected namespaces. It does not
restrict egress in this first policy. That preserves DNS, database, image, and
external API traffic until each application’s egress requirements are known.

Use a temporary test namespace and an explicit probe before enabling this in a
live environment. A policy object existing in Kubernetes is not proof that the
CNI enforces it.
