#!/bin/bash

set -o nounset
set -o errexit

export POSTGRESQL_USERNAME="${POSTGRESQL_USERNAME:-lm}"
export POSTGRESQL_DATABASE="${POSTGRESQL_DATABASE:-lm}"
export KEY=${LIFEMONITOR_TLS_KEY:-/certs/lm.key}
export CERT=${LIFEMONITOR_TLS_CERT:-/certs/lm.crt}
export GUNICORN_CONF="${GUNICORN_CONF:-/lm/gunicorn.conf.py}"

# wait for services
wait-for-postgres.sh
wait-for-redis.sh

if [[ "${FLASK_ENV}" == "development" || "${FLASK_ENV}" == "testingSupport" ]]; then
  printf "Staring app in DEV mode (Flask built-in web server with auto reloading)"
  python "${HOME}/app.py"
else
  PROMETHEUS_MULTIPROC_DIR=${PROMETHEUS_MULTIPROC_DIR:-}
  if [[ -z ${PROMETHEUS_MULTIPROC_DIR} ]]; then
    metrics_base_path="/tmp/lifemonitor/metrics"
    mkdir -p ${metrics_base_path}
    export PROMETHEUS_MULTIPROC_DIR=$(mktemp -d ${metrics_base_path}/backend.XXXXXXXX)
  fi

  # gunicorn settings
  export GUNICORN_SERVER="true"
  export GUNICORN_WORKERS="${GUNICORN_WORKERS:-2}"
  export GUNICORN_THREADS="${GUNICORN_THREADS:-1}"
  export GUNICORN_MAX_REQUESTS="${GUNICORN_MAX_REQUESTS:-0}"
  export GUNICORN_MAX_REQUESTS_JITTER="${GUNICORN_MAX_REQUESTS_JITTER:-0}"
  export GUNICORN_WORKER_CONNECTIONS="${GUNICORN_WORKER_CONNECTIONS:-1000}"
  export GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-30}"
  export GUNICORN_GRACEFUL_TIMEOUT="${GUNICORN_GRACEFUL_TIMEOUT:-30}"
  export GUNICORN_KEEPALIVE="${GUNICORN_KEEPALIVE:-2}"

  # run app with gunicorn
  printf "Starting app in PROD mode (Gunicorn)"
  gunicorn  --workers "${GUNICORN_WORKERS}"  \
            --threads "${GUNICORN_THREADS}" \
            --max_requests "${GUNICORN_MAX_REQUESTS}"
            --max_requests_jitter "${GUNICORN_MAX_REQUESTS_JITTER}" \
            --worker_connections "${GUNICORN_WORKER_CONNECTIONS}" \
            --worker_class "${GUNICORN_WORKER_CLASS}" \
            --timeout "${GUNICORN_TIMEOUT}" \
            --graceful_timeout "${GUNICORN_GRACEFUL_TIMEOUT}" \
            --keepalive "${GUNICORN_KEEPALIVE}" \
            --config "${GUNICORN_CONF}" \
            --certfile="${CERT}" --keyfile="${KEY}" \
            -b "0.0.0.0:8000" \
            "app"
fi
