#!/bin/bash

set -o nounset
set -o errexit

export POSTGRESQL_USERNAME="${POSTGRESQL_USERNAME:-lm}"
export POSTGRESQL_DATABASE="${POSTGRESQL_DATABASE:-lm}"

printf "Waiting for postgresql...\n" >&2
wait-for-postgres.sh
printf "DB is ready.  Starting application\n" >&2
if [[ "${FLASK_ENV}" == "development" ]]; then
  printf "Staring app in DEV mode (Flask built-in web server with auto reloading)"
  python "${HOME}/run.py"
else
  gunicorn --workers "${GUNICORN_WORKERS}"  \
           --threads "${GUNICORN_THREADS}" \
           -b "0.0.0.0:8000" \
           "lifemonitor.app:create_app()"
fi
