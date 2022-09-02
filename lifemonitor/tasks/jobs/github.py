
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
    logger.debug("Repositories: %r", repositories)

    repo_info = event.repository_reference
    logger.debug("Repo reference: %r", repo_info)

    repo = repo_info.repository
    logger.debug("Repository: %r", repo)

    logger.debug("Ref: %r", repo.ref)
    logger.debug("Refs: %r", repo.git_refs_url)
    logger.debug("Tree: %r", repo.trees_url)
    logger.debug("Commit: %r", repo.rev)

    event_handler = get_event_handler(e.type)
    logger.debug("Event handler: %r", event_handler)
    if event_handler:
        return event_handler(e)

    logger.warning("No handler for GitHub event: %r", e.type)
