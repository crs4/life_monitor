
import atexit
import logging
import re
from threading import local as thread_local

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.results.backends import RedisBackend
from dramatiq.results import Results
from flask_apscheduler import APScheduler

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
    # redis_uri = app.config.get("DRAMATIQ_BROKER_URL", "redis://localhost:6379/0")
    # logger.info("Setting up task queue.  Pointing to broker %s",
    #            re.sub(r'[^@]*@', '', redis_uri))  # before logging erase user:pass, if present

    logger.info("Setting up task queue -> hardcoded values!.")
    # redis_broker = RedisBroker(url=redis_uri)
    # result_backend = RedisBackend(url=redis_uri)
    redis_broker = RedisBroker(host="redis", password="foobar")
    result_backend = RedisBackend(host="redis", password="foobar")
    redis_broker.add_middleware(Results(backend=result_backend))
    dramatiq.set_broker(redis_broker)
    redis_broker.add_middleware(AppContextMiddleware(app))
    app.broker = redis_broker

    if not app.config.get('WORKER', False):
        logger.info("Starting periodic task scheduler")
        app.scheduler = APScheduler()
        app.scheduler.init_app(app)
        from . import tasks  # imported for its side effects - it defines the tasks
        app.scheduler.start()
        # Shut down the scheduler when exiting the app
        atexit.register(app.scheduler.shutdown)
    else:
        logger.info("Running app in worker process.  Not starting job scheduler")
