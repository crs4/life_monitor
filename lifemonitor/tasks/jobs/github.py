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

import logging

from apscheduler.triggers.cron import CronTrigger

from lifemonitor.auth.models import User
from lifemonitor.integrations.github import LifeMonitorGithubApp
from lifemonitor.integrations.github.controllers import get_event_handler
from lifemonitor.integrations.github.events import GithubEvent

from ..scheduler import TASK_EXPIRATION_TIME, schedule

# set module level logger
logger = logging.getLogger(__name__)


logger.info("Importing task definitions")


@schedule(name="ping", queue_name="github")
def ping(name: str = "Unknown"):
    logger.info(f"Pong, {name}")
    return "pong"


@schedule(name='githubEventHandler', queue_name="github", options={'max_retries': 0, 'max_age': TASK_EXPIRATION_TIME})
def handle_event(event):
    logger.debug("Github event: %r", event)

    e = GithubEvent.from_json(event)
    logger.debug(e)
    logger.debug(e.headers)
    logger.debug(e._raw_data)

    logger.debug(e.action)
    logger.debug(e.application)

    event = e
    logger.debug("Push event: %r", event)
    try:
        logger.debug("Event ref: %r", event.repository_reference.branch or event.repository_reference.tag)
        installation = event.installation
        logger.debug("Installation: %r", installation)
        repositories = installation.get_repos()
        for r in repositories:
            logger.debug("Processing repo: %r", r)
    except Exception as e:
        logger.debug(e)

    # Dispatch event to the proper handler
    event_handler = get_event_handler(event.type)
    logger.debug("Event handler: %r", event_handler)
    if event_handler:
        try:
            return event_handler(event)
        except Exception as e:
            logger.error(e)
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)

    logger.warning("No handler for GitHub event: %r", event.type)


@schedule(trigger=CronTrigger(minute=0, hour=4),
          queue_name='github', options={'max_retries': 0, 'max_age': TASK_EXPIRATION_TIME})
def check_installations():
    gh_app = LifeMonitorGithubApp.get_instance()
    installations = [str(_.id) for _ in gh_app.installations]
    logger.debug("Installations: %r", installations)
    for u in User.all():
        for i in u.github_settings.installations:
            installation_id = str(i['info']['id'])
            if installation_id not in installations:
                u.github_settings.remove_installation(installation_id)
                logger.info(f"Installation {installation_id} removed from account of user '{u.id}'")
            else:
                logger.debug(f"Installation {installation_id} still alive")
        u.save()
