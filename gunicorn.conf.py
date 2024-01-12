# Copyright (c) 2020-2024 CRS4
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

import os
import sys

from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics


def when_ready(server):
    print("Using", os.environ['PROMETHEUS_MULTIPROC_DIR'], " as PROMETHEUS_MULTIPROC_DIR", file=sys.stderr)
    # Fix the initialization of the backward compatible var `prometheus_multiproc_dir`.
    # This fix can go away in future releases of prometheus-client library
    # when the backward compatibility will be removed.
    if 'PROMETHEUS_MULTIPROC_DIR' in os.environ and 'prometheus_multiproc_dir' not in os.environ:
        os.environ["prometheus_multiproc_dir"] = os.environ['PROMETHEUS_MULTIPROC_DIR']
    metrics_port = int(os.environ.get('PROMETHEUS_METRICS_PORT', 9090))
    print("Starting metrics server on port", metrics_port, file=sys.stderr)
    GunicornPrometheusMetrics.start_http_server_when_ready(port=metrics_port)


def child_exit(server, worker):
    GunicornPrometheusMetrics.mark_process_dead_on_child_exit(worker.pid)
