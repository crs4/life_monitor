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

printf "Starting application\n" >&2
python3 "app.py"
