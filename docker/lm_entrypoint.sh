#!/bin/bash

set -o nounset
set -o errexit

export POSTGRESQL_USERNAME="${POSTGRESQL_USERNAME:-lm}"
export POSTGRESQL_DATABASE="${POSTGRESQL_DATABASE:-lm}"
export KEY=${LIFEMONITOR_TLS_KEY:-/certs/lm.key}
export CERT=${LIFEMONITOR_TLS_CERT:-/certs/lm.crt}
export GUNICORN_CONF="${GUNICORN_CONF:-/lm/gunicorn.conf.py}"

printf "Waiting for postgresql...\n" >&2
wait-for-postgres.sh
printf "DB is ready.  Starting application\n" >&2
if [[ "${FLASK_ENV}" == "development" || "${FLASK_ENV}" == "testingSupport" ]]; then
  printf "Staring app in DEV mode (Flask built-in web server with auto reloading)"
  python "${HOME}/app.py"
else
  if [[ -z ${PROMETHEUS_MULTIPROC_DIR} ]]; then
    export PROMETHEUS_MULTIPROC_DIR=$(mktemp -d /tmp/lifemonitor_prometheus_multiproc_dir.XXXXXXXX)
  fi
  gunicorn --workers "${GUNICORN_WORKERS}"  \
           --threads "${GUNICORN_THREADS}" \
           --config "${GUNICORN_CONF}" \
           --certfile="${CERT}" --keyfile="${KEY}" \
           -b "0.0.0.0:8000" \
           "app"
fi
