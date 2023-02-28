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
  export GUNICORN_SERVER="true"
  gunicorn --workers "${GUNICORN_WORKERS}"  \
           --threads "${GUNICORN_THREADS}" \
           --config "${GUNICORN_CONF}" \
           --certfile="${CERT}" --keyfile="${KEY}" \
           -b "0.0.0.0:8000" \
           "app"
fi
