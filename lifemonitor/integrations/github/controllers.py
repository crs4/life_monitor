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

from flask import Blueprint, Flask, current_app, request
from flask_apscheduler import APScheduler
from lifemonitor import cache
from lifemonitor.api.models import WorkflowRegistry
from lifemonitor.api.models.issues.common import MissingWorkflowFile
from lifemonitor.api.models.repositories.github import GithubWorkflowRepository
from lifemonitor.api.models.testsuites.testinstance import TestInstance
from lifemonitor.api.models.wizards import QuestionStep, UpdateStep
from lifemonitor.integrations.github import pull_requests
from lifemonitor.integrations.github.app import LifeMonitorGithubApp
from lifemonitor.integrations.github.events import GithubEvent
from lifemonitor.integrations.github.issues import GithubIssue
from lifemonitor.integrations.github.settings import GithubUserSettings
from lifemonitor.integrations.github.utils import delete_branch, match_ref
from lifemonitor.integrations.github.wizards import GithubWizard

from . import services

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
        logger.debug("Repo reference: %r", repo_info)

        repo: GithubWorkflowRepository = repo_info.repository
        logger.debug("Repository: %r", repo)

        logger.debug("Ref: %r", repo.ref)
        logger.debug("Refs: %r", repo.git_refs_url)
        logger.debug("Tree: %r", repo.trees_url)
        logger.debug("Commit: %r", repo.rev)

        # Configure registries
        registries = []
        if repo.config:
            logger.debug("Configuring registries from repository config: %r", repo.config)
            if repo_info.branch and repo_info.branch in repo.config.branches:
                registries.extend(repo.config.branches[repo_info.branch].get('update_registries', []))
            elif repo_info.tag and repo_info.tag in repo.config.tags:
                registries.extend(repo.config.tags[repo_info.tag].get('update_registries', []))
        else:
            logger.debug("Using all available registries")
            registries.extend([_.name for _ in WorkflowRegistry.all()])
        logger.debug("Registries: %r", registries)

        # filter branches and tags according to global and current repo settings
        settings: GithubUserSettings = event.sender.user.github_settings
        if not repo.config and \
            (repo_info.tag and (
                settings.all_tags or settings.is_valid_tag(repo_info.tag)) or repo_info.branch and (
                    settings.all_branches or settings.is_valid_branch(repo_info.branch))) or\
                repo.config and (match_ref(repo_info.tag, repo.config.tags) or match_ref(repo_info.branch, repo.config.branches)):
            register = not repo_info.deleted
            logger.debug("Repo to register: %r", register)
            if register:
                if settings.check_issues and (not repo.config or repo.config.checker_enabled):
                    check_result = services.check_repository_issues(repo_info)
                    if check_result.found_issues():
                        register = False
                        logger.warning("Found issue on repo: %r", repo_info)
                else:
                    logger.debug("Check for issues on '%s' ... SKIPPED", repo_info)
            if register:
                # register or update workflow on LifeMonitor and optionally on registries
                registered_workflow = services.register_repository_workflow(repo_info, registries=registries)
                logger.debug("Registered workflow: %r", registered_workflow)

            # delete the workflow version on LifeMonitor and optionally on registries
            if repo_info.ref and repo_info.deleted:
                services.delete_repository_workflow_version(repo_info, registries=registries)
        else:
            logger.info(f"Repo branch or tag {repo_info.ref} skipped!")

        return "No content", 204
    except Exception as e:
        logger.error(str(e))
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        return "Internal Error", 500


def issues(event: GithubEvent):
    logger.debug("Event: %r", event)

    # detect Github issue
    issue: GithubIssue = event.issue
    logger.debug("The current github issue: %r", event.issue)
    if not issue:
        logger.debug("No issue on this Github event")
        return "No issue", 204

    # delete support branch of closed issues
    if event.action == "closed":
        delete_branch(event.repository_reference.repository, issue)

    # check the author of the current issue
    if issue.user.login != event.application.bot:
        logger.debug("Nothing to do: issue not created by LifeMonitor[Bot]")
        return f"Issue not created by {event.application.bot}", 204

    # react only when the issue is opened
    if event.action == "opened":
        repository_issue = issue.as_repository_issue()
        logger.debug("LifeMonitor issue: %r", repository_issue)
        if repository_issue:
            logger.debug("Entering: %r", isinstance(repository_issue, MissingWorkflowFile))
            if isinstance(repository_issue, MissingWorkflowFile):
                logger.debug("Missing workflow file issue")

                wizard = GithubWizard.from_event(event)
                logger.debug("Current wizard: %r", wizard)
                if wizard:
                    if not wizard.current_step:
                        next_step = wizard.get_next_step()
                        logger.debug("Next step: %r", next_step)
                        wizard.io_handler.write(next_step)

    return "No action", 204


def issue_comment(event: GithubEvent):

    logger.debug("Event: %r", event)

    # detect Github issue
    issue: GithubIssue = event.issue
    logger.debug("The current github issue: %r", event.issue)
    if not issue:
        logger.debug("No issue associated with the current Github event: %r", event)
        return "No issue found", 204

    # check the author of the current issue
    if issue.user.login != event.application.bot:
        logger.debug("Nothing to do: issue not created by LifeMonitor[Bot]")
        return f"Issue not created by {event.application.bot}", 204

    if event.comment is None:
        logger.debug("No issue comment associated with the current Github event: %r", event)
        return "No issue comment", 204

    # check the author of the current issue comment
    if event.comment.user.login == event.application.bot:
        logger.debug("Nothing to do: comment crated by the LifeMonitor Bot")
        return f"Issue comment not created by {event.application.bot}", 204

    # check if there exists a candidate wizard for the current github event
    wizard = GithubWizard.from_event(event)
    logger.debug("Detected wizard: %r", wizard)
    if wizard:
        step = wizard.current_step
        logger.debug("The current step: %r %r", step, step.wizard)

        if isinstance(step, QuestionStep):
            answer = step.get_answer()
            logger.debug("The answer: %r", answer)
            if answer:
                logger.debug("The answer: %r", answer.body)
                answer.create_reaction("+1")
                next_step = step.next
                logger.debug("Next step: %r", next_step)
                if next_step:
                    if isinstance(next_step, UpdateStep):
                        repo = event.repository_reference.repository
                        logger.debug("REF: %r", repo.ref)
                        logger.debug("REV: %r", repo.rev)
                        logger.debug("DEFAULT BRANCH: %r", repo.default_branch)
                        if not pull_requests.find_pull_request_by_title(repo, next_step.title):
                            pr = pull_requests.create_pull_request(
                                repo, next_step.id, next_step.title, next_step.description, next_step.get_files(repo), allow_update=True)
                            logger.debug("PR created or updated: %r", pr)
                            if not pr:
                                return "Nothing to do", 204
                            else:
                                issue.create_comment(next_step.as_string() + f"<br>See PR {pr.html_url}")
                    else:
                        wizard.io_handler.write(next_step)
            else:
                # Unable to understand user answer
                logger.debug("Unable to understand user answer")
                event.comment.create_reaction("confused")
                wizard.io_handler.write(step)

        return f"Processed step {step.title} of wizard {wizard.title}", 204

    return "No action", 204


# Register Handlers
__event_handlers__ = {
    "ping": ping,
    "workflow_run": refresh_workflow_builds,
    "installation": installation,
    "push": push,
    "issues": issues,
    "issue_comment": issue_comment
}


# Integration Blueprint
blueprint = Blueprint("github_integration", __name__,
                      template_folder='templates',
                      static_folder="static", static_url_path='/static')


def event_handler_wrapper(app, handler, event):
    logger.debug("Current app: %r", app)
    logger.debug("Current handler: %r", handler)
    logger.debug("Current event: %r", event)
    with app.app_context():
        return handler(event)


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
    if event.repository_reference.branch and event.repository_reference.branch.startswith('lifemonitor-issue'):
        msg = f"Nothing to do for the event '{event.type}' on branch {event.repository_reference.branch}"
        logger.debug(msg)
        return msg, 204
    event_handler = __event_handlers__.get(event.type, None)
    logger.debug("Event: %r", event)
    if not event_handler:
        action = f"- action: {event._raw_data.get('action')}" if event._raw_data.get('action', None) else None
        logger.warning(f"No event handler registered for the event GitHub event '{event.type}' {action}")
        return f"No handler registered for the '{event.type}' event", 204
    else:
        app = current_app
        logger.debug("Current app: %r", app)
        scheduler: APScheduler = app.scheduler
        logger.debug("Current app scheduler: %r", scheduler)
        scheduler.add_job(event.id, event_handler_wrapper, args=[scheduler.app, event_handler, event], replace_existing=True)
        return "Event handler scheduled", 200


def init_integration(app: Flask):
    try:
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
    except Exception as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        logger.warning("Unable to initialize Github App integration: %r", str(e))
