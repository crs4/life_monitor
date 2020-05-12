#!/bin/bash

## Taken from the docker-compose docs:  https://docs.docker.com/compose/startup-order/

set -e

until PGPASSWORD=${POSTGRESQL_PASSWORD} psql -h "${POSTGRESQL_HOST}" -U "${POSTGRESQL_USERNAME}" ${POSTGRESQL_DATABASE} -c '\q'; do 
  >&2 echo "PostgreSQL is unavailable -- sleep 2 seconds and retry" ;
  sleep 2 ;
done ;
echo "PostgreSQL ready"
