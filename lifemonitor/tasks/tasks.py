
import logging

import dramatiq
import flask
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from lifemonitor.cache import Timeout

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
def heartbeat():
    logger.info("Heartbeat!")


@schedule(IntervalTrigger(seconds=Timeout.WORKFLOW * 3 / 4))
@dramatiq.actor
def check_workflows():
    from flask import current_app
    from lifemonitor.api.controllers import workflows_rocrate_download
    from lifemonitor.api.models import Workflow
    from lifemonitor.auth.services import login_user, logout_user
    from lifemonitor.cache import cache

    logger.info("Starting 'check_workflows' task....")
    for w in Workflow.all():
        try:
            for v in w.versions.values():
                with v.cache.transaction(str(v)):
                    logger.info("Updating external link: %r", v.external_link)
                    u = v.submitter
                    with current_app.test_request_context():
                        try:
                            if u is not None:
                                login_user(u)
                            logger.info("Updating RO-Crate...")
                            workflows_rocrate_download(w.uuid, v.version)
                            logger.info("Updating RO-Crate... DONE")
                        except Exception as e:
                            logger.error(f"Error when updating the workflow {w}: {str(e)}")
                            if logger.isEnabledFor(logging.DEBUG):
                                logger.exception(e)
                        finally:
                            try:
                                logout_user()
                            except Exception as e:
                                logger.debug(e)
        except Exception as e:
            logger.error("Error when executing task 'check_workflows': %s", str(e))
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
    logger.info("Starting 'check_workflows' task.... DONE!")


@schedule(IntervalTrigger(seconds=Timeout.BUILD * 3 / 4))
@dramatiq.actor
def check_last_build():
    from lifemonitor.api.models import Workflow
    from lifemonitor.cache import cache

    logger.info("Starting 'check_last build' task...")
    for w in Workflow.all():
        try:
            for s in w.latest_version.test_suites:
                logger.info("Updating workflow: %r", w)
                for i in s.test_instances:
                    with i.cache.transaction(str(i)):
                        builds = i.get_test_builds()
                        logger.debug("Updating latest builds: %r", builds)
                        for b in builds:
                            logger.debug("Updating build: %r", i.get_test_build(b.id))
                        logger.debug("Updating latest build: %r", i.last_test_build)
        except Exception as e:
            logger.error("Error when executing task 'check_last_build': %s", str(e))
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
    logger.info("Checking last build: DONE!")
