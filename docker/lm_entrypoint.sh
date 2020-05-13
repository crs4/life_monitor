#!/bin/bash

set -o nounset
set -o errexit

printf "Waiting for postgresql...\n" >&2
wait-for-postgres.sh
printf "DB is ready.  Starting application\n" >&2
python3 "${HOME}/lifemonitor/api.py"
