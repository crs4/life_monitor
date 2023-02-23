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

DEBUG="${DEBUG:-}"
FLASK_ENV="${FLASK_ENV:-production}"
if [[ "${FLASK_ENV}" == "development" ]]; then
  DEBUG="${DEBUG:-1}"
fi

# Create a directory for the worker's prometheus client if it doesn't exist yet
PROMETHEUS_MULTIPROC_DIR=${PROMETHEUS_MULTIPROC_DIR:-}
if [[ -z ${PROMETHEUS_MULTIPROC_DIR} ]]; then
  metrics_base_path="/tmp/lifemonitor/metrics"
  mkdir -p ${metrics_base_path}
  export PROMETHEUS_MULTIPROC_DIR=$(mktemp -d ${metrics_base_path}/worker.XXXXXXXX)
fi

# dramatiq looks at the following two env variables
# ( instructions in the dramatiq documentation
#   https://dramatiq.io/advanced.html#gotchas-with-prometheus )
export prometheus_multiproc_dir="${PROMETHEUS_MULTIPROC_DIR}"
export dramatiq_prom_db="${PROMETHEUS_MULTIPROC_DIR}"

log "Starting task queue worker container"
debug_log "PROMETHEUS_MULTIPROC_DIR = ${PROMETHEUS_MULTIPROC_DIR}"

if [[ -n "${DEBUG:-}" ]]; then
  watch='--watch .'
  verbose='--verbose'
  log "Worker watching source code directory"
fi

# Set worker processes
# WORKER_PROCESSES=1
processes=""
if [[ -n "${WORKER_PROCESSES:-}" ]]; then
  processes="--processes ${WORKER_PROCESSES}"
  log "Worker starting ${WORKER_PROCESSES} processes"
fi

# Set worker threads
# WORKER_THREADS=1
threads=""
if [[ -n "${WORKER_THREADS:-}" ]]; then
  threads="--threads ${WORKER_THREADS}"
  log "Worker starting with ${WORKER_THREADS} threads per process"
fi

# Set worker queues
#WORKER_QUEUES="heartbeat"
queues=""
if [[ -n "${WORKER_QUEUES:-}" ]]; then
  queues="--queues ${WORKER_QUEUES}"
  log "Worker starting to listen queues: ${WORKER_QUEUES}"
fi

# Start worker processes/threads
while : ; do
  /usr/local/bin/dramatiq \
    ${verbose:-} \
    ${watch:-} \
    ${processes:-} \
    ${threads:-} \
    lifemonitor.tasks.worker:broker lifemonitor.tasks ${queues}
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
