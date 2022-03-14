# Copyright (c) 2020-2021 CRS4
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

from __future__ import annotations

import logging

from flask import Blueprint, Flask, request
from lifemonitor import cache
from lifemonitor.api.models.repositories.github import GithubWorkflowRepository
from lifemonitor.api.models.testsuites.testinstance import TestInstance
from lifemonitor.integrations.github.app import LifeMonitorGithubApp
from lifemonitor.integrations.github.events import GithubEvent
from lifemonitor.integrations.github.services import check_repository

# Config a module level logger
logger = logging.getLogger(__name__)


def ping(event: GithubEvent):
    logger.debug("Ping event: %r", event)
    return "Pong", 200


def refresh_workflow_builds(event: GithubEvent):
    try:
        logger.debug("Workflow run event: %r", event)
        repository = event['payload']['repository']
        logger.debug("Workflow repository: %r", repository)
        workflow = event['payload']['workflow']
        logger.debug("Workflow: %r", workflow)
        workflow_run = event['payload']['workflow_run']
        logger.debug("Workflow run: %r", workflow_run)
        workflow_name = workflow['path'].replace('.github/workflows/', '')
        logger.debug("Workflow NAME: %r", workflow_name)
        workflow_resource = f"repos/{repository['full_name']}/actions/workflows/{workflow_name}"
        logger.debug("Workflow Resource: %r", workflow_resource)
        instances = TestInstance.find_by_resource(workflow_resource)
        logger.debug("Instances: %r", instances)
        with cache.transaction():
            for i in instances:
                i.get_test_builds(limit=10)
                i.get_test_build(workflow_run['id'])
                i.last_test_build
        return f"Test instance related with resource '{workflow_resource}' updated", 200
    except Exception as e:
        logger.error(e)
        return "Internal Error", 500


def installation(event: GithubEvent):
    try:
        logger.debug("Installation event: %r", event)
        return "No content", 204
    except Exception as e:
        logger.error(e)
        return "Internal Error", 500


def push(event: GithubEvent):
    try:
        logger.debug("Push event: %r", event)
        logger.debug("Event ref: %r", event.repository_reference.branch or event.repository_reference.tag)

        installation = event.installation
        logger.debug("Installation: %r", installation)

        repositories = installation.get_repos()
        logger.debug("Repositories: %r", repositories)

        repo_info = event.repository_reference
        logger.debug(repo_info)

        repo: GithubWorkflowRepository = repo_info.repository
        logger.debug("Repository: %r", repo)

        watched_branches = ('main')
        if repo_info.tag and repo_info.created or\
                repo_info.branch and repo_info.branch in watched_branches:
            check_result = check_repository_issues(repo_info)

        return "No content", 204
    except Exception as e:
        logger.error(str(e))
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        return "Internal Error", 500


# Register Handlers
__event_handlers__ = {
    "ping": ping,
    "workflow_run": refresh_workflow_builds,
    "installation": installation,
    "push": push
}


# Integration Blueprint
blueprint = Blueprint("github_integration", __name__,
                      template_folder='templates',
                      static_folder="static", static_url_path='/static')


@blueprint.route("/integrations/github", methods=("POST",))
def handle_event():
    logger.debug("Request header keys: %r", [k for k in request.headers.keys()])
    logger.debug("Request header values: %r", request.headers)
    if not LifeMonitorGithubApp.check_initialization():
        return "GitHub Integration not configured", 503
    valid = LifeMonitorGithubApp.validate_signature(request)
    logger.debug("Signature valid?: %r", valid)
    if not valid:
        return "Signature Invalid", 401
    event = GithubEvent.from_request()
    if event.repository_reference.branch.startswith('lifemonitor-issue'):
        return f"Nothing to do for the event '{event.type}' on branch {event.repository_reference.branch}", 204
    event_handler = __event_handlers__.get(event.type, None)
    logger.debug("Event: %r", event)
    if not event_handler:
        action = f"- action: {event._raw_data.get('action')}" if event._raw_data.get('action', None) else None
        logger.warning(f"No event handler registered for the event GitHub event '{event.type}' {action}")
        return f"No handler registered for the '{event.type}' event", 204
    else:
        return event_handler(event)


def init_integration(app: Flask):
    # Initialize GitHub App Integration
    app_identifier = app.config.get('GITHUB_INTEGRATION_APP_ID')
    webhook_secret = app.config.get('GITHUB_INTEGRATION_WEB_SECRET')
    service_token = app.config.get('GITHUB_INTEGRATION_SERVICE_TOKEN')
    service_repository = app.config.get('GITHUB_INTEGRATION_SERVICE_REPOSITORY')
    private_key_path = app.config.get('GITHUB_INTEGRATION_PRIVATE_KEY_PATH')
    LifeMonitorGithubApp.init(app_identifier, private_key_path, webhook_secret, service_token,
                              service_repository_full_name=service_repository)
    app.register_blueprint(blueprint)
    logger.info("Integration registered for GitHub App: %r", app_identifier)
