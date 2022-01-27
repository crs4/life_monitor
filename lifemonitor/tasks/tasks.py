
import logging

import dramatiq
import flask
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from lifemonitor.api.models.testsuites.testbuild import BuildStatus
from lifemonitor.api.serializers import BuildSummarySchema
from lifemonitor.auth.models import Notification
from lifemonitor.cache import Timeout
from lifemonitor.mail import send_notification

# set module level logger
logger = logging.getLogger(__name__)

# set expiration time (in msec) of tasks
TASK_EXPIRATION_TIME = 30000


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
@dramatiq.actor(max_retries=3, max_age=TASK_EXPIRATION_TIME)
def heartbeat():
    logger.info("Heartbeat!")


@schedule(IntervalTrigger(seconds=Timeout.WORKFLOW * 3 / 4))
@dramatiq.actor(max_retries=3, max_age=TASK_EXPIRATION_TIME)
def check_workflows():
    from flask import current_app
    from lifemonitor.api.controllers import workflows_rocrate_download
    from lifemonitor.api.models import Workflow
    from lifemonitor.auth.services import login_user, logout_user

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
@dramatiq.actor(max_retries=3, max_age=TASK_EXPIRATION_TIME)
def check_last_build():
    from lifemonitor.api.models import Workflow

    logger.info("Starting 'check_last build' task...")
    for w in Workflow.all():
        try:
            for s in w.latest_version.test_suites:
                logger.info("Updating workflow: %r", w)
                for i in s.test_instances:
                    with i.cache.transaction(str(i)):
                        builds = i.get_test_builds(limit=10)
                        logger.info("Updating latest builds: %r", builds)
                        for b in builds:
                            logger.info("Updating build: %r", i.get_test_build(b.id))
                        last_build = i.last_test_build
                        logger.info("Updating latest build: %r", last_build)
                        if last_build.status == BuildStatus.FAILED:
                            notification_name = f"{last_build} FAILED"
                            if len(Notification.find_by_name(notification_name)) == 0:
                                users = {s.user for s in w.subscriptions if s.user.email_notifications_enabled}
                                users.update({v.submitter for v in w.versions.values() if v.submitter.email_notifications_enabled})
                                users.update({s.user for v in w.versions.values() for s in v.subscriptions if s.user.email_notifications_enabled})
                                n = Notification(Notification.Types.BUILD_FAILED.name,
                                                 notification_name,
                                                 {'build': BuildSummarySchema().dump(last_build)},
                                                 users)
                                n.save()
        except Exception as e:
            logger.error("Error when executing task 'check_last_build': %s", str(e))
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
    logger.info("Checking last build: DONE!")


@schedule(IntervalTrigger(seconds=60))
@dramatiq.actor(max_retries=0, max_age=TASK_EXPIRATION_TIME)
def send_email_notifications():
    notifications = Notification.not_emailed()
    logger.info("Found %r notifications to send by email", len(notifications))
    count = 0
    for n in notifications:
        logger.debug("Processing notification %r ...", n)
        recipients = [u.user.email for u in n.users
                      if u.emailed is None and u.user.email is not None]
        sent = send_notification(n, recipients)
        logger.debug("Notification email sent: %r", sent is not None)
        if sent:
            logger.debug("Notification '%r' sent by email @ %r", n.id, sent)
            for u in n.users:
                if u.user.email in recipients:
                    u.emailed = sent
            n.save()
            count += 1
        logger.debug("Processing notification %r ... DONE", n)
    logger.info("%r notifications sent by email", count)
