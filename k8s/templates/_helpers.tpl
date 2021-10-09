{{/*
Expand the name of the chart.
*/}}
{{- define "chart.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "chart.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "chart.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{/*
Common labels
*/}}
{{- define "chart.labels" -}}
app.kubernetes.io/name: {{ include "chart.name" . }}
helm.sh/chart: {{ include "chart.chart" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "chart.selectorLabels" -}}
app.kubernetes.io/name: {{ include "chart.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "chart.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "chart.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Define environment variables shared by some pods.
*/}}
{{- define "lifemonitor.common-env" -}}
- name: HOME
  value: "/lm"
- name: FLASK_ENV
  value: "{{ .Values.lifemonitor.environment }}"
- name: POSTGRESQL_HOST
  value: {{ include "chart.fullname" . }}-postgresql
- name: POSTGRESQL_PORT
  value: "{{ .Values.postgresql.service.port }}"
- name: POSTGRESQL_USERNAME
  value: "{{ .Values.postgresql.postgresqlUsername }}"
- name: POSTGRESQL_PASSWORD
  value: "{{ .Values.postgresql.postgresqlPassword }}"
- name: POSTGRESQL_DATABASE
  value: "{{ .Values.postgresql.postgresqlDatabase }}"
- name: LIFEMONITOR_TLS_KEY
  value: "/lm/certs/tls.key"
- name: LIFEMONITOR_TLS_CERT
  value: "/lm/certs/tls.crt"
{{- end -}}

{{/*
Define volumes shared by some pods.
*/}}
{{- define "lifemonitor.common-volume" -}}
- name: lifemonitor-tls
  secret:
    secretName: lifemonitor-tls
- name: lifemonitor-settings
  secret:
    secretName: {{ include "chart.fullname" . }}-settings
{{- end -}}

{{/*
Define mount points shared by some pods.
*/}}
{{- define "lifemonitor.common-volume-mounts" -}}
- mountPath: "/lm/certs/"
  name: lifemonitor-tls
  readOnly: true
- name: lifemonitor-settings
  mountPath: "/lm/settings.conf"
  subPath: settings.conf
{{- end -}}
