#!/bin/bash

set -o nounset
set -o errexit

export POSTGRESQL_USERNAME="${POSTGRESQL_USERNAME:-lm}"
export POSTGRESQL_DATABASE="${POSTGRESQL_DATABASE:-lm}"
export KEY=${TLS_KEY:-/certs/lm.key}
export CERT=${TLS_CERT:-/certs/lm.crt}

printf "Waiting for postgresql...\n" >&2
wait-for-postgres.sh
printf "DB is ready.  Starting application\n" >&2
if [[ "${FLASK_ENV}" == "development" || "${FLASK_ENV}" == "testingSupport" ]]; then
  printf "Staring app in DEV mode (Flask built-in web server with auto reloading)"
  python "${HOME}/app.py"
else
  gunicorn --workers "${GUNICORN_WORKERS}"  \
           --threads "${GUNICORN_THREADS}" \
           --certfile="${CERT}" --keyfile="${KEY}" \
           -b "0.0.0.0:8000" \
           "app"
fi
