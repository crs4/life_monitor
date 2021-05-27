
import os
import sys

from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics


def when_ready(server):
    print("Using", os.environ['PROMETHEUS_MULTIPROC_DIR'], " as PROMETHEUS_MULTIPROC_DIR", file=sys.stderr)
    metrics_port = int(os.environ.get('PROMETHEUS_METRICS_PORT', 9090))
    print("Starting metrics server on port", metrics_port, file=sys.stderr)
    GunicornPrometheusMetrics.start_http_server_when_ready(port=metrics_port)


def child_exit(server, worker):
    GunicornPrometheusMetrics.mark_process_dead_on_child_exit(worker.pid)
