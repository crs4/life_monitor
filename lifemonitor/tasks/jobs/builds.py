
import datetime
import logging
import time

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from lifemonitor.api.models.notifications import WorkflowStatusNotification
from lifemonitor.api.models.testsuites.testbuild import BuildStatus, TestBuild
from lifemonitor.api.serializers import BuildSummarySchema
from lifemonitor.auth.models import (EventType, Notification)
from lifemonitor.cache import Timeout
from lifemonitor.tasks.scheduler import TASK_EXPIRATION_TIME, schedule
from lifemonitor.utils import notify_workflow_version_updates

# set module level logger
logger = logging.getLogger(__name__)


logger.info("Importing task definitions")


@schedule(trigger=IntervalTrigger(seconds=Timeout.WORKFLOW * 3 / 4),
          queue_name='builds', options={'max_retries': 3, 'max_age': TASK_EXPIRATION_TIME})
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


@schedule(trigger=IntervalTrigger(seconds=Timeout.BUILD * 3 / 4),
          queue_name='builds', options={'max_retries': 3, 'max_age': TASK_EXPIRATION_TIME})
def check_last_build():
    from lifemonitor.api.models import Workflow

    logger.info("Starting 'check_last build' task...")
    for w in Workflow.all():
        try:
            for workflow_version in w.versions.values():
                if workflow_version and len(workflow_version.github_versions) > 0:
                    logger.warning("Workflow skipped because updated via github app")
                    continue
                for s in workflow_version.test_suites:
                    logger.info("Updating workflow: %r", w)
                    for i in s.test_instances:
                        # old_builds = i.get_test_builds(limit=10)
                        with i.cache.transaction(str(i)):
                            builds = i.get_test_builds(limit=10)
                            logger.info("Updating latest builds: %r", builds)
                            for b in builds:
                                logger.info("Updating build: %r", i.get_test_build(b.id))
                            i.save(commit=False, flush=False)
                            workflow_version.save()
                            notify_workflow_version_updates([workflow_version], type='sync')
                            last_build = i.last_test_build
                            logger.debug("Latest build: %r", last_build)

                            # check state transition
                            if last_build:
                                logger.debug("Latest build status: %r", last_build.status)
                                failed = last_build.status == BuildStatus.FAILED
                                if len(builds) == 1 or \
                                        builds[0].status in (BuildStatus.FAILED, BuildStatus.PASSED) and \
                                        builds[1].status in (BuildStatus.FAILED, BuildStatus.PASSED) and \
                                        len(builds) > 1 and builds[1].status != last_build.status:
                                    logger.error("Updating latest build: %r", last_build)
                                    notification_name = f"{last_build} {'FAILED' if failed else 'RECOVERED'}"
                                    if len(Notification.find_by_name(notification_name)) == 0:
                                        users = workflow_version.workflow.get_subscribers()
                                        n = WorkflowStatusNotification(
                                            EventType.BUILD_FAILED if failed else EventType.BUILD_RECOVERED,
                                            notification_name,
                                            {'build': BuildSummarySchema(exclude_nested=False).dump(last_build)},
                                            users)
                                        n.save()
                # save workflow version and notify updates
                workflow_version.save()
                notify_workflow_version_updates([workflow_version], type='sync')
        except Exception as e:
            logger.error("Error when executing task 'check_last_build': %s", str(e))
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
    logger.info("Checking last build: DONE!")


@schedule(trigger=CronTrigger(minute=0, hour=2),
          queue_name='builds', options={'max_retries': 3, 'max_age': TASK_EXPIRATION_TIME})
def periodic_builds():
    from lifemonitor.api.models import Workflow

    logger.info("Running 'periodic builds' task...")
    for w in Workflow.all():

        for workflow_version in w.versions.values():
            for s in workflow_version.test_suites:
                for i in s.test_instances:
                    try:
                        last_build: TestBuild = i.last_test_build
                        if datetime.datetime.fromtimestamp(last_build.timestamp) \
                                + datetime.timedelta(minutes=1) < datetime.datetime.now():
                            logger.info("Triggering build of test suite %s on test instance %s for workflow version %s", s, i, workflow_version)
                            i.start_test_build()
                            time.sleep(10)
                        else:
                            logger.warning("Skipping %s (last build: %s)",
                                           i, datetime.datetime.fromtimestamp(last_build.timestamp))
                    except Exception as e:
                        logger.error("Error when starting periodic build on test instance %s: %s", i, str(e))
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.exception(e)
    logger.info("Running 'periodic builds': DONE!")
