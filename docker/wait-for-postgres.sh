#!/bin/bash

## Taken from the docker-compose docs:  https://docs.docker.com/compose/startup-order/

set -e

echo "Verifying that db is ready..."

until PGPASSWORD=${POSTGRESQL_PASSWORD} psql \
    "--host=${POSTGRESQL_HOST}" \
    "--username=${POSTGRESQL_USERNAME}" \
    "--dbname=${POSTGRESQL_DATABASE}" \
    '--command=\q'; do 
  >&2 echo "PostgreSQL is unavailable -- sleeping 2 seconds then retrying"
  sleep 2
done

echo "PostgreSQL ready"
