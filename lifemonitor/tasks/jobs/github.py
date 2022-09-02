
import logging

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
    logger.debug("Event ref: %r", event.repository_reference.branch or event.repository_reference.tag)

    installation = event.installation
    logger.debug("Installation: %r", installation)

    repositories = installation.get_repos()
    for r in repositories:
        logger.debug("Processing repo: %r", r)

    event_handler = get_event_handler(e.type)
    logger.debug("Event handler: %r", event_handler)
    if event_handler:
        return event_handler(e)

    logger.warning("No handler for GitHub event: %r", e.type)
