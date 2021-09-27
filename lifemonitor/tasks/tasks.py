
import logging

import dramatiq
import flask

# set module level logger
logger = logging.getLogger(__name__)


def schedule(trigger):
    def decorator(actor):
        app = flask.current_app
        # Check whether the app has a scheduler attribute.
        # When we run as a worker, the app is created but the
        # scheduler is not initialized.
        fn_name = f"{actor.fn.__module__}.{actor.fn.__name__}"
        if hasattr(app, "scheduler"):
            logger.debug("Scheduling function %s with trigger %r", fn_name, trigger)
            flask.current_app.scheduler.add_job(id=fn_name, func=actor.send, trigger=trigger, replace_existing=True)
        else:
            logger.debug("Schedule %s no-op - scheduler not initialized", fn_name)
        return actor
    return decorator


@dramatiq.actor(max_retries=2, store_results=True)
def add(x, y):
    r = int(x) + int(y)
    logger.info("The <add> actor.  The sum of %s and %s = %s", x, y, r)
    return r


from apscheduler.triggers.cron import CronTrigger


logger.info("Importing task definitions")
@schedule(CronTrigger(second=0))
@dramatiq.actor
def hearbeat():
    logger.info("Heartbeat!")
