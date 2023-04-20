#!/bin/bash

set -o nounset
set -o errexit

function debug_log() {
  if [[ -n "${DEBUG:-}" ]]; then
    log "${@}"
  fi
}

function log() {
  printf "%s [wait-for-file] %s\n" "$(date +"%F %T")" "${*}" >&2
}

file="${1:-}"
timeout=${2:-0}

if [[ -z ${file} ]]; then
    log "You need to provide a filename"
    exit 1
fi

log "Waiting for file ${file} (timeout: ${timeout})..."

if [[ -e "$file" ]]; then
    log "File ${file} found!"
    exit 0
fi

if ((timeout > 0)); then
    end_time=$((SECONDS + timeout))
    while [[ ! -e "$file" && $SECONDS -lt $end_time ]]; do
        debug_log "File not found ${file} found... retry within 1 sec"
        sleep 1
    done
else
    while [[ ! -e "$file" ]]; do
        debug_log "File not found ${file} found... retry within 1 sec"
        sleep 1
    done
fi

if [[ -e "$file" ]]; then
    log "File ${file} found!"
    exit 0
else
    log "File ${file} not found!"
    exit 1
fi

