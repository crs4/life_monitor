# Copyright (c) 2020-2022 CRS4
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
import os
import uuid
from tempfile import TemporaryDirectory
from typing import Any, Callable, Dict, List, Optional, Union

import requests
from flask import (Blueprint, Flask, current_app, redirect, render_template,
                   request)
from flask_login import login_required
from github.PullRequest import PullRequest

from lifemonitor import cache
from lifemonitor.api import serializers
from lifemonitor.api.models import WorkflowRegistry
from lifemonitor.api.models.registries.settings import RegistrySettings
from lifemonitor.api.models.repositories.config import WorkflowRepositoryConfig
from lifemonitor.api.models.repositories.github import GithubWorkflowRepository
from lifemonitor.api.models.testsuites.testinstance import TestInstance
from lifemonitor.api.models.wizards import QuestionStep, UpdateStep
from lifemonitor.api.models.workflows import WorkflowVersion
from lifemonitor.auth.models import User
from lifemonitor.auth.oauth2.client.models import OAuthIdentity
from lifemonitor.auth.services import authorized, current_user
from lifemonitor.integrations.github import pull_requests
from lifemonitor.integrations.github.app import LifeMonitorGithubApp
from lifemonitor.integrations.github.events import (GithubEvent,
                                                    GithubRepositoryReference)
from lifemonitor.integrations.github.issues import GithubIssue
from lifemonitor.integrations.github.notifications import \
    GithubWorkflowVersionNotification
from lifemonitor.integrations.github.settings import GithubUserSettings
from lifemonitor.integrations.github.utils import delete_branch
from lifemonitor.integrations.github.wizards import GithubWizard
from lifemonitor.tasks import Scheduler
from lifemonitor.utils import (bool_from_string, get_git_repo_revision,
                               match_ref)

from . import services

# Config a module level logger
logger = logging.getLogger(__name__)


def ping(event: GithubEvent):
    logger.debug("Ping event: %r", event)
    return "Pong", 200


def refresh_workflow_builds(event: GithubEvent):
    try:

        logger.debug("Workflow run event: %r", event)

        installation = event.installation
        logger.debug("Installation: %r", installation)

        repo_info = event.repository_reference
        logger.debug("Repo reference: %r", repo_info)

        repo: GithubWorkflowRepository = repo_info.repository
        logger.debug("Repository: %r", repo)

        github_workflow = event.workflow
        logger.debug("Github Workflow: %r (name: %s, path: %s)",
                     github_workflow, github_workflow.name, github_workflow.path)

        github_workflow_run = event.workflow_run
        logger.debug("Github Workflow: %r", github_workflow_run)

        repo_revision = get_git_repo_revision(repo.local_repo.local_path, github_workflow_run.raw_data['head_sha'])
        refs = [_['ref'].split('/')[-1] for _ in repo_revision['refs']]
        logger.debug("REFS: %r", refs)

        workflow_name = github_workflow.path.replace('.github/workflows/', '')
        logger.debug("Workflow NAME: %r", workflow_name)

        workflow_resource = f"repos/{repo.full_name}/actions/workflows/{workflow_name}"
        logger.debug("Workflow Resource: %r", workflow_resource)
        instances = TestInstance.find_by_resource(workflow_resource)
        logger.debug("Instances: %r", instances)

        with cache.cache.transaction():
            for i in instances:
                workflow_version = i.test_suite.workflow_version
                if workflow_version.version in refs or (not workflow_version.has_revision() and not workflow_version.next_version):
                    logger.warning("Version %r to uodate", workflow_version)
                    i.get_test_build(f"{github_workflow_run.id}_{github_workflow_run.raw_data['run_attempt']}")
                    i.test_suite.workflow_version.status
                else:
                    logger.warning("Skipping instance %r not bound to the current branch or tag", i)
        return f"Test instance related with resource '{workflow_resource}' updated", 200
    except Exception as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        logger.error(e)
        return "Internal Error", 500


def refresh_workflow_build(event: GithubEvent):
    try:

        logger.debug("Workflow run event: %r", event)

        installation = event.installation
        logger.debug("Installation: %r", installation)

        repo_info = event.repository_reference
        logger.debug("Repo reference: %r", repo_info)

        workflow_job = event._raw_data.get('workflow_job', None)
        logger.debug("workflow job: %r", workflow_job)

        repo: GithubWorkflowRepository = repo_info.repository
        logger.debug("Repository: %r", repo)

        repo_revision = get_git_repo_revision(repo.local_repo.local_path, workflow_job['head_sha'])
        refs = [_['ref'].split('/')[-1] for _ in repo_revision['refs']]
        logger.debug("REFS: %r", refs)

        github_workflow_run = event.workflow_run
        logger.debug("Github Workflow: %r", github_workflow_run)

        workflow_name = github_workflow_run.raw_data['path'].replace('.github/workflows/', '')
        logger.debug("Workflow NAME: %r", workflow_name)

        build_id = event.workflow_build_id
        logger.debug("Workflow build ID: %r", build_id)

        if build_id:
            workflow_resource = f"repos/{repo.full_name}/actions/workflows/{workflow_name}"
            logger.debug("Workflow Resource: %r", workflow_resource)
            instances = TestInstance.find_by_resource(workflow_resource)
            logger.debug("Instances: %r", instances)

            with cache.cache.transaction():
                for i in instances:
                    logger.warning("Checking version %s in refs %r", i.test_suite.workflow_version, refs)
                    workflow_version = i.test_suite.workflow_version
                    if not workflow_version:
                        raise RuntimeError("No workflow version associated with test instance %r", i)
                    if workflow_version.version in refs or not workflow_version.has_revision():
                        logger.warning("Version %s in refs %r", i.test_suite.workflow_version.version, refs)
                        last_build_id = f"{github_workflow_run.id}_{github_workflow_run.raw_data['run_attempt']}"
                        i.get_test_build(last_build_id)
                        i.test_suite.workflow_version.status
                        logger.info("Version %s updated... last build: %s", i.test_suite.workflow_version.version, last_build_id)
                    else:
                        logger.warning("Version %s not in refs %r", i.test_suite.workflow_version.version, refs)
            return f"Test instance related with resource '{workflow_resource}' updated", 200
        else:
            return "No build attached to the current event", 204
    except Exception as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        logger.error(e)
        return "Internal Error", 500


def installation_repositories(event: GithubEvent):
    try:
        if event.action in ['created', 'added']:

            installation = event.installation
            logger.debug("App Installation: %r", installation)

            repositories = event.repositories_added
            logger.debug("App installed on Repositories: %r", repositories)

            for repo_info in repositories:
                logger.debug("Repo reference: %r", repo_info)
                logger.debug("Repo ref: %r", repo_info.branch or repo_info.tag)

                repo: GithubWorkflowRepository = repo_info.repository
                logger.debug("Repository: %r", repo)

                logger.debug("Ref: %r", repo.ref)
                logger.debug("Refs: %r", repo.git_refs_url)
                logger.debug("Tree: %r", repo.trees_url)
                logger.debug("Commit: %r", repo.rev)

                logger.warning("Is Tag: %r", repo_info.tag)
                logger.warning("Is Branch: %r", repo_info.branch)

                if event.action in ['created', 'added']:
                    if not repo_info.ref or repo_info.deleted:
                        logger.debug("Repo ref not defined or branch/tag deleted: %r", repo)
                    else:
                        settings: GithubUserSettings = event.sender.user.github_settings
                        __check_for_issues_and_register__(repo_info, settings,
                                                          event.sender.user.registry_settings, True)

        elif event.action == 'deleted':
            installation = event.installation
            logger.debug("App Installation: %r", installation)

            repositories = event.repositories_removed
            logger.debug("App installed on Repositories: %r", repositories)

    except Exception as e:
        logger.error(str(e))
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)


def __notify_workflow_version_event__(repo_reference: GithubRepositoryReference,
                                      workflow_version: Union[WorkflowVersion, Dict],
                                      action: str):
    try:
        notification_enabled = True
        repo: GithubWorkflowRepository = repo_reference.repository
        pattern = None
        ref_type = 'branches' if repo_reference.branch else 'tags'
        try:
            if hasattr(repo.config, ref_type):
                ref_list = getattr(repo.config, ref_type)
                ref = repo_reference.branch or repo_reference.tag
                _, pattern = match_ref(ref, ref_list)
                if pattern:
                    notification_enabled = ref_list[pattern].get('enable_notifications', True)
                    logger.debug("Notifications enabled for '%s': %r", pattern, notification_enabled)
                else:
                    logger.debug("No notification setting found for repo %s (ref: %s)", repo.full_name, ref)
        except AttributeError as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
        logger.debug("Notifications enabled: %r", notification_enabled)
        if notification_enabled:
            logger.debug(f"Setting notification for action '{action}' on repo '{repo.full_name}' (ref: {repo.ref})")
            identity = OAuthIdentity.find_by_provider_user_id(str(repo.owner.id), "github")
            if identity:
                version = workflow_version if isinstance(workflow_version, dict) else serializers.WorkflowVersionSchema(exclude=('meta', 'links')).dump(workflow_version)
                repo_data = repo.raw_data
                repo_data['ref'] = repo.ref
                n = GithubWorkflowVersionNotification(workflow_version=version, repository=repo_data, action=action, users=[identity.user])
                n.save()
                logger.debug(f"Setting notification for action '{action}' on repo '{repo.full_name}' (ref: {repo.ref})")
            else:
                logger.warning("Unable to find user identity associated to repo: %r", repo)
        else:
            logger.warning("Notification disabled for %r (ref %r)", repo_reference.full_name, pattern)
    except Exception as e:
        logger.error(f"Unable to notify workflow version event: {str(e)}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)


def __config_registry_list__(repo_info: GithubRepositoryReference,
                             registry_settings: RegistrySettings) -> List[str]:
    # Configure registries
    registries = []
    repo: GithubWorkflowRepository = repo_info.repository
    if repo.config:
        logger.debug("Configuring registries from repository config: %r", repo.config)
        if repo_info.branch and match_ref(repo_info.branch, repo.config.branches):
            registries.extend(repo.config.branches[repo_info.branch].get('update_registries', []))
        elif repo_info.tag:
            tag, pattern = match_ref(repo_info.tag, repo.config.tags)
            if tag:
                registries.extend(repo.config.tags[pattern].get('update_registries', []))
    else:
        logger.debug("Using all available registries")
        registries.extend([_.name for _ in WorkflowRegistry.all()])
    # use only registries globally enabled on Github Integration Settings
    enabled_registries = [_ for _ in registries if _ in registry_settings.registries]
    logger.warning("The following registries will be ignored because globally disabled: %r", [_ for _ in registries if _ not in enabled_registries])
    logger.debug("Filtered registries: %r", enabled_registries)
    return enabled_registries


def __skip_branch_or_tag__(repo_info: GithubRepositoryReference,
                           user_settings: GithubUserSettings):
    repo: GithubWorkflowRepository = repo_info.repository
    if repo.config:
        if not repo.config.is_valid:
            return False
        if match_ref(repo_info.tag, repo.config.tags):
            return False
        if match_ref(repo_info.branch, repo.config.branches):
            return False
    elif repo_info.tag:
        if user_settings.all_tags or user_settings.is_valid_tag(repo_info.tag):
            return False
    elif repo_info.branch:
        if user_settings.all_branches or user_settings.is_valid_branch(repo_info.branch):
            return False
    return True


def __forward_event__(event: GithubEvent) -> Optional[Dict]:
    repo_info = event.repository_reference
    logger.debug("Repo reference: %r", repo_info)

    repo: GithubWorkflowRepository = repo_info.repository
    logger.debug("Repository: %r", repo)

    config: WorkflowRepositoryConfig = repo.config
    if not config:
        logger.debug("No config file found")
        return None

    logger.error("Workflow repository config: %r", config._raw_data)

    ref = repo_info.branch or repo_info.tag
    logger.error("Ref: %s", ref)

    ref_settings = repo.config.get_ref_settings(ref)
    logger.warning("Repo ref settings: %r", ref_settings)

    default_instance_info = current_app.config['PROXY_ENTRIES']['default']
    logger.debug("Default LM instance: %r", default_instance_info)

    if ref_settings:
        lm_instance_name = ref_settings.get('lifemonitor_instance', None)
        if lm_instance_name:
            lm_instance_info = current_app.config['PROXY_ENTRIES'][lm_instance_name]
            assert lm_instance_info, "Undefined instance info"
            if lm_instance_info['url'] != default_instance_info['url']:
                logger.warning("Using LM instance: %r", lm_instance_info)
                redirect_url = os.path.join(lm_instance_info['url'], 'integrations/github')
                logger.debug("Redirecting to: %r", redirect_url)
                response = requests.request(
                    method=request.method,
                    url=redirect_url,
                    headers={key: value for (key, value) in request.headers if key != 'Host'},
                    data=request.get_data(),
                    cookies=request.cookies,
                    allow_redirects=False,
                    stream=True)
                logger.debug("Respose: %r", response.content)
                return lm_instance_info
        else:
            logger.debug("No settings found for ref: %s", ref)

    # Fall back to the default/current LifeMonitor instance
    logger.warning("Using default lifemonitor: %s", default_instance_info)
    return None


def __check_for_issues_and_register__(repo_info: GithubRepositoryReference,
                                      github_settings: GithubUserSettings,
                                      registry_settings: RegistrySettings,
                                      check_issues: bool = True):
    # enable/disable registry integration according to settings
    register = bool_from_string(current_app.config['ENABLE_REGISTRY_INTEGRATION']) if current_app else False
    # set repo
    repo: GithubWorkflowRepository = repo_info.repository
    logger.debug("Repo to register: %r", repo)
    # filter branches and tags according to global and current repo settings
    if __skip_branch_or_tag__(repo_info, github_settings):
        logger.info(f"Repo branch or tag {repo_info.ref} skipped!")
        return
    # check for issues (if enabled)
    if check_issues:
        if github_settings.check_issues and (not repo.config or repo.config.checker_enabled):
            check_result = services.check_repository_issues(repo_info)
            if check_result.found_issues():
                register = False
                logger.warning("Found issue on repo: %r", repo_info)
        else:
            logger.debug("Check for issues on '%s' ... SKIPPED", repo_info)
    # register workflow
    logger.debug("Process workflow registration: %r", register)
    if register:
        # Configure registries
        registries = __config_registry_list__(repo_info, registry_settings)
        logger.debug("Registries to update: %r", registries)
        # found the existing workflow associated with repo
        _, workflow_version = services.find_workflow_version(repo_info)
        # register or update workflow on LifeMonitor and optionally on registries
        registered_workflow = services.register_repository_workflow(repo_info, registries=registries)
        logger.debug("Registered workflow: %r", registered_workflow)
        if registered_workflow:
            __notify_workflow_version_event__(repo_info, registered_workflow, action='updated' if workflow_version else 'created')


def create(event: GithubEvent):
    logger.debug("Create event: %r", event)

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

    logger.warning("Is Tag: %r", repo_info.tag)
    logger.warning("Is Branch: %r", repo_info.branch)

    if repo_info.branch:
        try:
            __check_for_issues_and_register__(repo_info,
                                              event.sender.user.github_settings,
                                              event.sender.user.registry_settings,
                                              True)
        except Exception as e:
            logger.exception(e)


def delete(event: GithubEvent):
    logger.debug("Delete event: %r", event)

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

    logger.warning("Is Tag: %s", repo_info.tag)
    logger.warning("Is Branch: %s", repo_info.branch)

    if repo_info.tag or repo_info.branch:
        try:
            workflow_version = services.delete_repository_workflow_version(repo_info,
                                                                           registries=event.sender.user.registry_settings.registries)
            if workflow_version:
                __notify_workflow_version_event__(repo_info, workflow_version, action='deleted')
        except Exception as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)


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

        if not repo_info.ref or repo_info.deleted:
            logger.debug("Repo ref not defined or branch/tag deleted: %r", repo)
        else:
            settings: GithubUserSettings = event.sender.user.github_settings
            __check_for_issues_and_register__(repo_info, settings,
                                              event.sender.user.registry_settings, True)

        return "No content", 204
    except Exception as e:
        logger.error(str(e))
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        return "Internal Error", 500


def __delete_support_branches__(event: GithubEvent):
    repo = event.repository_reference
    logger.debug("Repo reference: %r", repo)

    # detect the current LifeMonitor issue
    issue_or_pullrequest = event.issue or event.pull_request
    issue = issue_or_pullrequest.as_repository_issue() if issue_or_pullrequest else None
    if not issue:
        logger.warning("No support branch to delete since no LifeMonitor issue has been detected")
        return

    # initialize support branches to delete
    support_branches = [issue.id]

    # check if the current issue is associated to a wizard
    wizard = GithubWizard.from_event(event)
    logger.debug("Detected wizard: %r", wizard)
    if wizard:
        current_step = wizard.current_step
        logger.debug("Detected wizard step: %r", current_step)
        if current_step:
            support_branches.append(current_step.id)

    # delete support branches
    logger.warning("Support branches to delete: %r", support_branches)
    for support_branch in support_branches:
        try:
            logger.debug("Trying to delete support branch: %s ...", support_branch)
            delete_branch(event.repository_reference.repository, support_branch)
            logger.debug("Support branch %s deleted", support_branch)
        except Exception as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
            logger.warn("Unable to delete support branch %s", support_branch)


def pull_request(event: GithubEvent):
    logger.debug("Event: %r", event)

    # detect Github issue
    pull_request: PullRequest = event.pull_request
    logger.debug("The current github pull_request: %r", pull_request)
    if not pull_request:
        logger.debug("No pull_request on this Github event")
        return "No issue", 204

    # check the author of the current pull_request
    if pull_request.user.login != event.application.bot:
        logger.debug("Nothing to do: pull request not created by LifeMonitor[Bot]")
        return f"Issue not created by {event.application.bot}", 204

    # set reference to PR HEAD
    ref = pull_request.head.ref
    logger.debug("HEAD of this PR: %s", ref)

    # delete support branch of closed issues
    if event.action == "closed":
        __delete_support_branches__(event)


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
        __delete_support_branches__(event)

    # check the author of the current issue
    if issue.user.login != event.application.bot:
        logger.debug("Nothing to do: issue not created by LifeMonitor[Bot]")
        return f"Issue not created by {event.application.bot}", 204

    # react only when the issue is opened
    if event.action == "opened":
        repository_issue = issue.as_repository_issue()
        logger.debug("LifeMonitor issue: %r", repository_issue)
        if repository_issue:
            wizard = GithubWizard.from_event(event)
            logger.debug("Current wizard: %r", wizard)
            if wizard:
                if not wizard.current_step:
                    next_step = wizard.get_next_step()
                    logger.debug("Next step: %r", next_step)
                    wizard.io_handler.write(next_step, append_help=True)

    return "No action", 204


def issue_comment(event: GithubEvent):

    logger.debug("Event: %r", event)

    # check if an issue comment has been detected
    if event.comment is None:
        logger.debug("No issue comment associated with the current Github event: %r", event)
        return "No issue comment", 204

    # check the author of the current issue comment
    # skip comment if generated by the LifeMonitor[bot]
    if event.comment.is_generated_by_bot():
        logger.debug("Nothing to do: issue not created by LifeMonitor[Bot]")
        return f"Comment created by {event.application.bot}", 204

    # check the recipient of the issue comment:
    # skip comment if not addressed to the LifeMonitor[bot]
    if not event.comment.is_addressed_to_bot():
        logger.debug(f"Generic message not addressed to {event.application.bot}")
        return

    # check the body of the issue comment:
    # skip comment if it is empty
    if not event.comment.body:
        logger.debug("Message empty: %r", event.comment.body)
        return

    logger.warning("Message: %r", event.comment.body)
    # detected a message for this LifeMonitor[bot]
    logger.error("Message to bot: %r - %r", event.comment.body, event.comment._body.value)
    wizard = GithubWizard.from_event(event)
    logger.warning("Wizard: %r", wizard)
    logger.warning("Step: %r", wizard.current_step)

    # return

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
                            issue.create_comment(
                                f"<b>{next_step.title}</b><br>Please wait, collecting files...")
                            with TemporaryDirectory(dir='/tmp') as target_path:
                                pr = pull_requests.create_pull_request_from_github_issue(
                                    repo, next_step.id, issue,
                                    next_step.get_files(repo, target_path=target_path), False,
                                    create_comment=next_step.as_string())
                                if not pr:
                                    logger.warning("Unable to create PR for issue: %r", issue)
                                # Uncomment to create a separate PR to propose changes
                                # pr = pull_requests.create_pull_request(
                                #     repo, next_step.id, next_step.title, next_step.description, next_step.get_files(repo), allow_update=True)
                                # logger.debug("PR created or updated: %r", pr)
                                # if not pr:
                                #     return "Nothing to do", 204
                                # else:
                                #     issue.create_comment(next_step.as_string() + f"<br>See PR {pr.html_url}")
                    else:
                        wizard.io_handler.write(next_step, append_help=True)
            else:
                # Unable to understand user answer
                logger.debug("Unable to understand user answer")
                event.comment.create_reaction("confused")
                wizard.io_handler.write(step, append_help=True)

        return f"Processed step {step.title} of wizard {wizard.title}", 204

    return "No action", 204


# Register Handlers
__event_handlers__ = {
    "ping": ping,
    "workflow_run": refresh_workflow_builds,
    "workflow_job": refresh_workflow_build,
    "installation": installation_repositories,
    "installation_repositories": installation_repositories,
    "push": push,
    "issues": issues,
    "issue_comment": issue_comment,
    "pull_request": pull_request,
    "create": create,
    "delete": delete
}


def get_event_handler(event_type: str) -> Callable:
    handler = __event_handlers__.get(event_type, None)
    logger.debug("Dispatching event %r to handler %r", event_type, handler)
    return handler


# Integration Blueprint
blueprint = Blueprint("github_integration", __name__,
                      template_folder='templates',
                      static_folder="static", static_url_path='/static')


@authorized
@blueprint.route("/integrations/github/installations/new", methods=("GET",))
def handle_registration_new():
    # get a reference to the LifeMonitor Github App
    gh_app = LifeMonitorGithubApp.get_instance()
    # build the current state
    state_id = uuid.uuid4()
    # state: Dict[str, Any] = _get_state()
    # save the created state on cache
    # cache.cache.set(f"{state_id}", state)
    # redirect to Github App registration endpoint
    return redirect(f'https://github.com/apps/{gh_app.name}/installations/new?state={state_id}')


@blueprint.route("/integrations/github/installations/callback", methods=("GET",))
@login_required
def handle_registration_callback():
    logger.debug(request.args)
    installation_id = request.args.get('installation_id', type=str)
    if not installation_id:
        return "Bad request: missing parameter 'installation_id'", 400
    setup_action = request.args.get('setup_action')
    if not setup_action:
        return "Bad request: missing parameter 'setup_action", 400
    # not used yet
    state = request.args.get('state', None)
    logger.debug("Callback state: %r", state)

    # get a reference to the LifeMonitor Github App
    gh_app = LifeMonitorGithubApp.get_instance()
    installation = gh_app.get_installation(int(installation_id))
    assert installation, "Installation not found"
    installation_repositories = {r.full_name: r.raw_data for r in installation.get_repos()}
    logger.debug("Installation repositories: %r", installation_repositories)

    logger.debug("Current user: %r", current_user)
    assert not current_user.is_anonymous  # type: ignore
    user: User = current_user  # type: ignore

    settings = GithubUserSettings(user) \
        if not user.github_settings else user.github_settings

    user_installation = settings.get_installation(installation_id)
    logger.debug(user_installation)
    user_installation_repositories = settings.get_installation_repositories(installation_id)
    logger.debug("User installation repos: %r", user_installation_repositories)

    # compute list of repositories added/removed
    logger.debug("Installation found on user settings")
    added_repos: Dict[str, Any] = {k: v for k, v in installation_repositories.items() if k not in user_installation_repositories}
    logger.debug("Added repositories: %r", added_repos)
    existing_repos: Dict[str, Any] = {r: v for r, v in user_installation_repositories.items() if r in installation_repositories}
    logger.debug("Existing repositories: %r", existing_repos)
    removed_repos: Dict[str, Any] = {k: v for k, v in user_installation_repositories.items() if k not in installation_repositories}
    logger.debug("Removed repositories: %r", removed_repos)

    if setup_action == 'delete':
        settings.remove_installation(installation_id)
        logger.debug(f"Installation {installation_id} removed")
        assert settings.get_installation(installation_id) is None, "Installation not removed"

    else:
        # creating or updating an installation
        if not user_installation:
            logger.debug(f"Installation {installation_id} not associated to the user account")
            settings.add_installation(installation_id, installation.raw_data)

        for r, v in added_repos.items():
            settings.add_installation_repository(installation_id, r, v)
            logger.debug(f"Repo {r} added to installation {installation_id}")
        for r in removed_repos:
            settings.remove_installation_repository(installation_id, r)
            logger.debug(f"Repo {r} removed from installation {installation_id}")

    # update user settings
    user.save()

    return render_template('github_integration/registration.j2',
                           installation=installation.raw_data, webapp_url=current_app.config['WEBAPP_URL'],
                           installation_repositories=settings.get_installation_repositories(installation_id).values(),
                           added_repos=added_repos.keys(), removed_repos=removed_repos.values())


@blueprint.route("/integrations/github", methods=("POST",))
def handle_event():
    logger.debug("Request header keys: %r", [k for k in request.headers.keys()])
    logger.debug("Request header values: %r", request.headers)
    if not LifeMonitorGithubApp.check_initialization():
        return "GitHub Integration not configured", 503

    # filter events: skip all push on branches generated by LifeMonitor
    event = GithubEvent.from_request()
    try:
        branch = event.repository_reference.branch
        if branch and (branch.startswith('lifemonitor-issue') or branch.startswith('wizard-step')):
            msg = f"Nothing to do for the event '{event.type}' on branch {event.repository_reference.branch}"
            logger.debug(msg)
            return msg, 204
    except ValueError as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        logger.debug(str(e))

    # check the author of the current pull_request
    if event.pusher == event.application.bot:
        logger.debug("Nothing to do: commit pushed by LifeMonitor[Bot]")
        return f"Push created by {event.application.bot}", 204

    # Validate message signature
    valid = LifeMonitorGithubApp.validate_signature(request)
    logger.debug("Signature valid?: %r", valid)
    if not valid:
        return "Signature Invalid", 401

    # Forward request to another LifeMonitor instance if required
    try:
        forwarded_to = __forward_event__(event)
        if forwarded_to:
            return f"Event forwarded to LifeMonitor instance '{forwarded_to['name']}' (url: {forwarded_to['url']})"
    except Exception as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(e)

    # Submit event to an async handler
    event_handler = __event_handlers__.get(event.type, None)
    logger.debug("Event: %r", event)
    if not event_handler:
        action = f"- action: {event._raw_data.get('action')}" if event._raw_data.get('action', None) else None
        logger.warning(f"No event handler registered for the event GitHub event '{event.type}' {action}")
        return f"No handler registered for the '{event.type}' event", 204
    else:
        app = current_app
        logger.debug("Current app: %r", app)
        scheduler: Scheduler = app.scheduler
        logger.debug("Current app scheduler: %r", scheduler)
        scheduler.run_job('githubEventHandler', event.to_json())
        return "OK", 200


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
