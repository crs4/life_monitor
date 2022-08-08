
import sys
import atexit
import logging
from threading import local as thread_local


from .jobs import load_job_modules
import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.results import Results
from dramatiq.results.backends.redis import RedisBackend
from flask_apscheduler import APScheduler

from lifemonitor.tasks.scheduler import Scheduler

REDIS_NAMESPACE = 'dramatiq'

logger = logging.getLogger(__name__)


class AppContextMiddleware(dramatiq.Middleware):
    state = thread_local()

    def __init__(self, app):
        self.app = app

    def before_process_message(self, broker, message):
        context = self.app.app_context()
        context.push()

        self.state.context = context

    def after_process_message(self, broker, message, *, result=None, exception=None):
        try:
            context = self.state.context
            context.pop(exception)
            del self.state.context
        except AttributeError:
            pass

    after_skip_message = after_process_message


def init_task_queue(app):
    # detect if we are running the main app or a custom command.
    command_line = ' '.join(sys.argv)
    is_main_flask_app = \
        ('app.py' in command_line) \
        or ('gunicorn' in command_line) \
        or ('dramatiq' in command_line)

    # initialize task queue only if running the main Flask app
    # if not is_main_flask_app:
    #     logger.debug("Running a Flask command: skip task queue initialisation")
    # else:
    redis_connection_params = dict(host=app.config.get("REDIS_HOST", "redis"),
                                   password=app.config.get("REDIS_PASSWORD", "foobar"),
                                   port=int(app.config.get("REDIS_PORT_NUMBER", 6379)))
    logger.info("Setting up task queue.  Pointing to broker %s:%s",
                redis_connection_params['host'], redis_connection_params['port'])
    redis_broker = RedisBroker(namespace=f"{REDIS_NAMESPACE}", **redis_connection_params)
    result_backend = RedisBackend(namespace=f"{REDIS_NAMESPACE}-results", **redis_connection_params)
    redis_broker.add_middleware(Results(backend=result_backend))
    dramatiq.set_broker(redis_broker)
    redis_broker.add_middleware(AppContextMiddleware(app))
    app.broker = redis_broker
    # Initialize task scheduler
    if not app.config.get('WORKER', False) or not is_main_flask_app:
        logger.info("Initializing job scheduler")
        app.scheduler = Scheduler()
        app.scheduler.init_app(app)
        # start the scheduler on the main app process
        if is_main_flask_app:
            logger.info("Starting job scheduler")
            app.scheduler.start()
            # Shut down the scheduler when exiting the app
            atexit.register(app.scheduler.shutdown)
    else:
        # When we run as a worker, the scheduler is initialized but not started
        logger.info("Running app in worker process")
    # load jobs
    if app.config.get('ENV') not in ['testingSupport', 'testing']:
        logger.debug("Loading job modules...")
        load_job_modules()
        logger.debug("Loading job modules... DONE")
