
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
