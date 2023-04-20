#!/bin/bash

# Copyright (c) 2020-2022 CRS4
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

set -o nounset
set -o errexit

export POSTGRESQL_USERNAME="${POSTGRESQL_USERNAME:-lm}"
export POSTGRESQL_DATABASE="${POSTGRESQL_DATABASE:-lm}"
export KEY=${LIFEMONITOR_TLS_KEY:-/certs/lm.key}
export CERT=${LIFEMONITOR_TLS_CERT:-/certs/lm.crt}

# set websocket server port
export WEBSOCKET_SERVER_PORT=${WEBSOCKET_SERVER_PORT:-8001}

# TODO: check if this flag is needed
export WEBSOCKET_SERVER="false"

# set switch to enable autoreload feature of gunicorn
export WEBSOCKET_SERVER_ENV=${WEBSOCKET_SERVER_ENV:-${FLASK_ENV:-production}}

# wait for services
wait-for-postgres.sh
wait-for-redis.sh

# Create a directory for the worker's prometheus client if it doesn't exist yet
PROMETHEUS_MULTIPROC_DIR=${PROMETHEUS_MULTIPROC_DIR:-}
if [[ -z ${PROMETHEUS_MULTIPROC_DIR} ]]; then
  metrics_base_path="/tmp/lifemonitor/metrics"
  mkdir -p ${metrics_base_path}
  export PROMETHEUS_MULTIPROC_DIR=$(mktemp -d ${metrics_base_path}/websocket-server.XXXXXXXX)
fi

# start gunicorn server
export GUNICORN_SERVER="true"
reload_opt=""
if [[ "${WEBSOCKET_SERVER_ENV}" == "development" ]]; then reload_opt="--reload"; fi
gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker --workers 1 \
         ${reload_opt} \
         --certfile="${CERT}" --keyfile="${KEY}" \
         -b 0.0.0.0:${WEBSOCKET_SERVER_PORT} ws


