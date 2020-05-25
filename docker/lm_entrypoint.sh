#!/bin/bash

set -o nounset
set -o errexit

export POSTGRESQL_USERNAME="${POSTGRESQL_USERNAME:-lm}"
export POSTGRESQL_DATABASE="${POSTGRESQL_DATABASE:-lm}"

printf "Waiting for postgresql...\n" >&2
wait-for-postgres.sh
printf "DB is ready.  Starting application\n" >&2
python3 "${HOME}/lifemonitor/api.py"
