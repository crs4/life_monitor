#!/bin/bash

set -o nounset
set -o errexit

function debug_log() {
  if [[ -n "${DEBUG:-}" ]]; then
    log "${@}"
  fi
}

function log() {
  printf "%s [worker_entrypoint] %s\n" "$(date +"%F %T")" "${*}" >&2
}

FLASK_ENV="${FLASK_ENV:-production}"
if [[ "${FLASK_ENV}" == "development" ]]; then
  DEBUG="${DEBUG:-1}"
fi

# Create a directory for the worker's prometheus client.
# We follow the instructions in the dramatiq documentation
#    https://dramatiq.io/advanced.html#gotchas-with-prometheus
export PROMETHEUS_MULTIPROC_DIR=$(mktemp -d /tmp/lm_dramatiq_prometheus_multiproc_dir.XXXXXXXX)
rm -rf "${PROMETHEUS_MULTIPROC_DIR}/*"
# dramatiq looks at the following two env variables
export prometheus_multiproc_dir="${PROMETHEUS_MULTIPROC_DIR}"
export dramatiq_prom_db="${PROMETHEUS_MULTIPROC_DIR}"

log "Starting task queue worker container"
debug_log "PROMETHEUS_MULTIPROC_DIR = ${PROMETHEUS_MULTIPROC_DIR}"

if [[ -n "${DEBUG:-}" ]]; then
  watch='--watch .'
  verbose='--verbose'
  log "Worker watching source code directory"
fi

if [[ -n "${WORKER_PROCESSES:-}" ]]; then
  processes="--processes ${WORKER_PROCESSES}"
  log "Worker starting ${WORKER_PROCESSES} processes"
fi

while : ; do
  /usr/local/bin/dramatiq \
    ${verbose:-} \
    ${watch:-} \
    ${processes:-} \
    lifemonitor.tasks.worker:broker lifemonitor.tasks.tasks
  exit_code=$?
  if [[ $exit_code == 3 ]]; then
    log "dramatiq worker could not connect to message broker (exit code ${exit_code})" 
    log "Restarting..."
  else
    break # out of the loop
  fi
done

log "Worker exiting with exit code ${exit_code}"

exit ${exit_code}
