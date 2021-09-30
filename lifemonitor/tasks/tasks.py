
import logging

import dramatiq
import flask
from apscheduler.triggers.cron import CronTrigger


# set module level logger
logger = logging.getLogger(__name__)


def schedule(trigger):
    """
    Decorator to add a scheduled job calling the wrapped function.
    :param  trigger:  an instance of any of the trigger types provided in apscheduler.triggers.
    """
    def decorator(actor):
        app = flask.current_app
        # Check whether the app has a scheduler attribute.
        # When we run as a worker, the app is created but the
        # scheduler is not initialized.
        fn_name = f"{actor.fn.__module__}.{actor.fn.__name__}"
        # We check to see whether the scheduler is available simply by verifying whether the
        # app has the `scheduler` attributed defined.
        # The LM app should have this; the worker app does not have it.
        if hasattr(app, "scheduler"):
            logger.debug("Scheduling function %s with trigger %r", fn_name, trigger)
            flask.current_app.scheduler.add_job(id=fn_name, func=actor.send, trigger=trigger, replace_existing=True)
        else:
            logger.debug("Schedule %s no-op - scheduler not initialized", fn_name)
        return actor
    return decorator


logger.info("Importing task definitions")


@schedule(CronTrigger(second=0))
@dramatiq.actor
def hearbeat():
    logger.info("Heartbeat!")
