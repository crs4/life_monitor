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
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: "{{ .Chart.Name }}-{{ .Chart.Version }}"
{{- end }}

{{/*
Selector labels
*/}}
{{- define "chart.selectorLabels" -}}
app.kubernetes.io/name: {{ include "chart.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Define lifemonitor image
*/}}
{{- define "chart.lifemonitor.image" -}}
{{- if .Values.lifemonitor.image }}
{{- printf "%s" .Values.lifemonitor.image }}
{{- else }}
{{- printf "crs4/lifemonitor:%s" .Chart.AppVersion }}
{{- end }}
{{- end }}


{{/*
Define lifemonitor TLS secret name
*/}}
{{- define "chart.lifemonitor.tls" -}}
{{- printf "%s-tls" .Release.Name }}
{{- end }}

{{/*
Define lifemonitor secret name for backup key
*/}}
{{- define "chart.lifemonitor.backup.key" -}}
{{- printf "%s-backup-key" .Release.Name }}
{{- end }}


{{/*
Define volume name of LifeMonitor backup data 
*/}}
{{- define "chart.lifemonitor.data.backup" -}}
{{- printf "data-%s-backup" .Release.Name }}
{{- end }}

{{/*
Define volume name of LifeMonitor workflows data
*/}}
{{- define "chart.lifemonitor.data.workflows" -}}
{{- printf "data-%s-workflows" .Release.Name }}
{{- end }}

{{/*
Define volume name of LifeMonitor logs data
*/}}
{{- define "chart.lifemonitor.data.logs" -}}
{{- printf "data-%s-logs" .Release.Name }}
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
- name: REDIS_HOST
  value: "{{ .Release.Name }}-redis-master"
- name: REDIS_PORT
  value: "{{ .Values.redis.master.service.port }}"
- name: REDIS_PASSWORD
  value: "{{ .Values.redis.auth.password }}"
- name: WORKER_PROCESSES
  value: "{{ .Values.worker.processes }}"
- name: WORKER_THREADS
  value: "{{ .Values.worker.threads }}"
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
    secretName: {{ include "chart.lifemonitor.tls" . }}
- name: lifemonitor-settings
  secret:
    secretName: {{ include "chart.fullname" . }}-settings
- name: lifemonitor-logs
  emptyDir: {}
- name: lifemonitor-data
  persistentVolumeClaim:
    claimName: data-{{- .Release.Name -}}-workflows
{{- if .Values.integrations -}}
{{- range $k, $v := .Values.integrations }}
{{- if $v.private_key }}
- name: lifemonitor-{{ $k }}-key
  secret:
    secretName: {{ $v.private_key.secret }}
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Define mount points shared by some pods.
*/}}
{{- define "lifemonitor.common-volume-mounts" -}}
- mountPath: "/lm/certs/"
  name: lifemonitor-tls
  readOnly: true
- name: lifemonitor-logs
  mountPath: "/var/log"
- name: lifemonitor-settings
  mountPath: "/lm/settings.conf"
  subPath: settings.conf
{{- if not .Values.remoteStorage.enabled }}
- name: lifemonitor-data
  mountPath: "/var/data/lm"
{{- end -}}
{{- if .Values.integrations -}}
{{- range $k, $v := .Values.integrations }}
{{- if $v.private_key }}
- name: lifemonitor-{{ $k }}-key
  mountPath: "/lm/integrations/{{ $k | lower }}"
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}


{{/*
Generate certificates for the LifeMonitor Api Server .
*/}}
{{- define "gen-certs" -}}
{{- $altNames := list ( printf "%s.%s" (include "chart.name" .) .Release.Namespace ) ( printf "%s.%s.svc" (include "chart.name" .) .Release.Namespace ) -}}
{{- $ca := genCA "lifemonitor-ca" 365 -}}
{{- $cert := genSignedCert ( include "chart.name" . ) nil $altNames 365 $ca -}}
tls.crt: {{ $cert.Cert | b64enc }}
tls.key: {{ $cert.Key | b64enc }}
{{- end -}}


{{/*
Define lifemonitor GithubApp secret name
*/}}
{{- define "chart.lifemonitor.githubApp.key" -}}
{{- printf "%s-ghapp-key" .Release.Name }}
{{- end }}

{{/*
Read and encode the GitHub App private key.
*/}}
{{- define "lifemonitor.githubApp.readPrivateKey" -}}
{{- $fileContent := $.Files.Get .Values.integrations.github.private_key.path -}}
{{- $base64Content := $fileContent | b64enc -}}
{{- printf "%s" $base64Content -}}
{{- end -}}


{{/*
Set the Rate Limiting configuration for the API server.
*/}}
{{- define "lifemonitor.api.rateLimiting" -}}
{{- if .Values.rateLimiting.zone.accounts.enabled -}}
{{- $delay := .Values.rateLimiting.zone.accounts.delay | int -}}
{{- $burst := .Values.rateLimiting.zone.accounts.burst | int }}
# Rate limiting for the /accounts endpoint
limit_req zone=api_accounts burst={{ $burst }} {{ if gt $delay 0 }}delay={{ $delay }}{{ else }}nodelay{{ end }};
limit_req_status 429;
{{- else }}
# Rate limiting disabled for the /accounts endpoint
{{- end -}}
{{- end -}}
