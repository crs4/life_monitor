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
- name: lifemonitor-data
  persistentVolumeClaim:
    claimName: data-{{- .Release.Name -}}-workflows
{{- if .Values.integrations -}}
{{- range $k, $v := .Values.integrations }}
- name: lifemonitor-{{ $k }}-key
  secret:
    secretName: {{ $v.private_key.secret }}
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
- name: lifemonitor-settings
  mountPath: "/lm/settings.conf"
  subPath: settings.conf
- name: lifemonitor-data
  mountPath: "/var/data/lm"
{{- if .Values.integrations -}}
{{- range $k, $v := .Values.integrations }}
- name: lifemonitor-{{ $k }}-key
  mountPath: "/lm/integrations/{{ $k | lower }}"
{{- end -}}
{{- end -}}
{{- end -}}


{{/*
Define command to mirror (cluster) local backup to a remote site via SFTP
*/}}
{{- define "backup.remote.command" -}}
{{- if and .Values.backup.remote .Values.backup.remote.enabled }}
{{- if eq (.Values.backup.remote.protocol | lower) "sftp" }}
{{- printf "lftp -c \"open -u %s,%s sftp://%s; mirror -e -R /var/data/backup %s \"" 
    .Values.backup.remote.user .Values.backup.remote.password 
    .Values.backup.remote.host .Values.backup.remote.path
}}
{{- else if eq (.Values.backup.remote.protocol | lower) "ftps" }}
{{- printf "lftp -c \"%s %s open -u %s,%s ftp://%s; mirror -e -R /var/data/backup %s \"" 
    "set ftp:ssl-auth TLS; set ftp:ssl-force true;"
    "set ftp:ssl-protect-list yes; set ftp:ssl-protect-data yes;"
    .Values.backup.remote.user .Values.backup.remote.password 
    .Values.backup.remote.host .Values.backup.remote.path
}}
{{- end }}
{{- end }}
{{- end }}