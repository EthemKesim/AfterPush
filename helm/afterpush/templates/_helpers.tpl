
{{/*
Return the Kubernetes resource identity.

Existing deployments retain application.name.
Project-aware deployments can provide application.resourceName.

The longest resource suffix is "-grafana-dashboard" (18 characters).
A 45-character base name keeps generated DNS-label resource names
within the 63-character limit.
*/}}
{{- define "afterpush.resourceName" -}}
{{- $name := .Values.application.resourceName | default .Values.application.name -}}
{{- if not (regexMatch "^[a-z0-9]([-a-z0-9]*[a-z0-9])?$" $name) -}}
{{- fail "application.resourceName must be a valid Kubernetes DNS label" -}}
{{- end -}}
{{- if gt (len $name) 45 -}}
{{- fail "application.resourceName must not exceed 45 characters because generated resources have suffixes" -}}
{{- end -}}
{{- $name -}}
{{- end -}}
