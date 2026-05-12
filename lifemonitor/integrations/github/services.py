# Copyright (c) 2020-2026 CRS4
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
from typing import Dict, List, Optional, Set, Tuple, Union

from lifemonitor.api import serializers
from lifemonitor.api.models.registries.registry import WorkflowRegistry
from lifemonitor.api.models.repositories.base import IssueCheckResult
from lifemonitor.api.models.repositories.github import GithubWorkflowRepository
from lifemonitor.api.models.workflows import Workflow, WorkflowVersion
from lifemonitor.api.services import LifeMonitor
from lifemonitor.auth.models import HostingService, User
from lifemonitor.auth.oauth2.client.models import (
    OAuthIdentity, OAuthIdentityNotFoundException)
from lifemonitor.integrations.github.events import (GithubEvent,
                                                    GithubRepositoryReference)
from lifemonitor.integrations.github.registry import (GithubWorkflowRegistry,
                                                      GithubWorkflowVersion)

from . import issues, pull_requests

# Config a module level logger
logger = logging.getLogger(__name__)


def ping(event: object):
    logger.debug("Ping event: %r", event)
    return "Pong", 200


def map_issues(check_result: IssueCheckResult):
    def _post_issue_messages(gh_issue, issue):
        for message in issue.get_messages():
            gh_issue.create_comment(f"<b>{message.type.name}:</b> {message.text}")
            logger.debug("Added issue message: %r", message)

    repo = check_result.repo
    for issue in check_result.checked:
        if issue in check_result.issues:
            try:
                gh_issue = issues.find_issue(repo, issue)
            except ValueError as e:
                gh_issue = None
                if logger.isEnabledFor(logging.DEBUG):
                    logger.exception(e)
            logger.debug("Found issue on GitHub? ->> %r", gh_issue)
            if not gh_issue:
                gh_issue = issues.create_issue(repo, issue)
                logger.debug("Created a new GitHub issue: %r", gh_issue)
                _post_issue_messages(gh_issue, issue)
                if issue.has_changes():
                    pull_requests.create_pull_request_from_github_issue(repo, issue.id, gh_issue, issue.get_changes(repo), allow_update=False)
            else:
                if issue.has_changes() and issue.enable_change_update:
                    pull_requests.create_pull_request_from_github_issue(
                        repo,
                        issue.id,
                        gh_issue,
                        issue.get_changes(repo),
                        allow_update=True,
                    )
                if issue.enable_message_updates:
                    _post_issue_messages(gh_issue, issue)
        else:
            logger.debug(f"Closing issue: {issue}")
            issues.close_issue(repo, issue)


def check_repository_issues(repository_reference: GithubRepositoryReference) -> IssueCheckResult:
    logger.debug("Repository ref: %r", repository_reference)
    repo: GithubWorkflowRepository = repository_reference.repository
    logger.debug("Repository: %r", repo)
    check_result = repo.check(fail_fast=True,
                              include=repo.config.include_issues if repo.config else None,
                              exclude=repo.config.exclude_issues if repo.config else None)
    logger.debug("Issue check result: %r", check_result)
    map_issues(check_result)
    return check_result


def __normalize_registry_identitiers__(registries: List[str], as_strings: bool = True):
    return [] if not registries else \
        [r if not as_strings else r.client_name
         for r in WorkflowRegistry.all() if r.client_name in registries or r.name in registries]


def __get_registries_map__(w: Workflow, registries: List[str]):
    registries_map = []
    for r_id in registries:
        r_wv = None
        versions = []
        for v in w.versions.values():
            r_wv = v.registry_workflow_versions.get(r_id, None)
            if r_wv:
                versions.append(r_wv)
        map_item = (r_id, versions[0].identifier if len(versions) > 0 else None, versions)
        if map_item not in registries_map:
            registries_map.append(map_item)
    return registries_map


def find_workflow_version(repository_reference: GithubRepositoryReference) -> Tuple[Optional[Workflow], Optional[WorkflowVersion]]:
    github_registry = get_event_github_registry(repository_reference.event)
    if not github_registry:
        logger.warning("Unable to load github registry for installation %r", repository_reference.event.installation_id)
        return None, None
    # find the workflow
    workflow_version = None
    workflow = github_registry.find_workflow(repository_reference.full_name)
    if workflow:
        # get the workflow version (the one associated with the branch or tag of the repository)
        workflow_version = workflow.versions.get(repository_reference.branch or repository_reference.tag, None)
        logger.debug("Found workflow version: %r", workflow_version)
    return workflow, workflow_version


def get_event_github_registry(event: GithubEvent) -> Optional[GithubWorkflowRegistry]:
    installation = None
    try:
        installation = event.installation
    except Exception as e:
        logger.warning("Unable to resolve installation %r", event.installation_id)
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
    if installation and installation.github_registry:
        return installation.github_registry

    try:
        app = event.application
    except Exception as e:
        logger.warning("Unable to resolve application for event %r", event.type)
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        return None
    if not app or not app.owner:
        logger.warning("Unable to resolve app owner for event %r", event.type)
        return None

    try:
        identity: OAuthIdentity = OAuthIdentity.find_by_provider_user_id(str(app.owner.id), "github")
    except OAuthIdentityNotFoundException as e:
        logger.warning("Github identity of app owner '%r' not found", app.owner.id)
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        return None

    try:
        installation_id = int(event.installation_id) if event.installation_id is not None else None
    except ValueError:
        logger.warning("Invalid installation id: %r", event.installation_id)
        return None

    if installation_id is None:
        logger.warning("Missing installation id for event %r", event.type)
        return None

    return GithubWorkflowRegistry.find(identity.user, app.id, installation_id)


def delete_event_github_registries(event: GithubEvent) -> int:
    try:
        app = event.application
    except Exception as e:
        logger.warning("Unable to resolve application for event %r", event.type)
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        return 0

    try:
        installation_id = int(event.installation_id) if event.installation_id is not None else None
    except ValueError:
        logger.warning("Invalid installation id: %r", event.installation_id)
        return 0

    if installation_id is None:
        logger.warning("Missing installation id for event %r", event.type)
        return 0

    deleted_count = GithubWorkflowRegistry.unregister_github_installation(app.id, installation_id, safe=True)
    logger.info("Deleted %d github registries for installation %r", deleted_count, installation_id)
    return deleted_count


def get_repository_refs_for_full_name(event: GithubEvent, repository_full_name: str) -> List[str]:
    registry = get_event_github_registry(event)
    if not registry:
        return []
    return sorted({_.repo_ref for _ in registry.workflow_versions
                   if _.repo_identifier == repository_full_name and _.repo_ref})


def get_tracked_repository_refs(event: GithubEvent) -> Dict[str, List[str]]:
    registry = get_event_github_registry(event)
    if not registry:
        return {}

    refs_map: Dict[str, Set[str]] = {}
    for workflow_version in registry.workflow_versions:
        if not workflow_version.repo_identifier:
            continue
        refs = refs_map.setdefault(workflow_version.repo_identifier, set())
        if workflow_version.repo_ref:
            refs.add(workflow_version.repo_ref)

    return {repo_full_name: sorted(refs) for repo_full_name, refs in refs_map.items()}


def get_repository_ref_settings(event: GithubEvent, repository_full_name: str,
                                repo_ref: Optional[str]) -> Optional[GithubWorkflowVersion]:
    registry = get_event_github_registry(event)
    if not registry:
        return None
    setting = registry.find_workflow_version_by_repo(repository_full_name, ref=repo_ref)
    if setting:
        return setting
    return registry.find_workflow_version_by_repo(repository_full_name)


def update_repository_ref_notifications(event: GithubEvent, repository_full_name: str,
                                        repo_ref: Optional[str], enabled: bool) -> None:
    setting = get_repository_ref_settings(event, repository_full_name, repo_ref)
    if not setting:
        logger.debug("No repository settings found for %s@%s", repository_full_name, repo_ref)
        return
    setting.notifications_enabled = enabled
    setting.save()


def get_repository_ref_notifications_enabled(event: GithubEvent, repository_full_name: str,
                                             repo_ref: Optional[str], default: bool = True) -> bool:
    setting = get_repository_ref_settings(event, repository_full_name, repo_ref)
    if not setting or setting.notifications_enabled is None:
        return default
    return setting.notifications_enabled


def identify_workflow_version_submitter(repository_reference: GithubRepositoryReference) -> Optional[User]:
    """ Identify the submitter of the workflow version.
    The submitter is the user who trigger a github event on the repository.
    If the "sender" of the event is not a LifeMonitor user, the submitter is the user who triggered the event
    for the registration of the first workflow version (e.g., the user who registered the LifeMonitor Github app on the github repository).
    """
    # search user identity
    submitter = None
    try:
        identity: OAuthIdentity = repository_reference.event.sender
        submitter = identity.user
        logger.debug("Found a Github identity for the sender %r --> %r, %r", repository_reference.event.sender, identity, submitter)
    except OAuthIdentityNotFoundException as e:
        logger.warning("Github identity of the sender '%r' doesn't match with any LifeMonitor user identity", repository_reference.owner_id)
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)

    # fallback the submitter to the original submitter of the workflow
    # (i.e., the user who registered the LifeMonitor Github app on the github repository)
    if not submitter:
        # get the workflow
        workflow, _ = find_workflow_version(repository_reference)
        if workflow:
            submitter = workflow.earliest_version.submitter

    return submitter


def register_repository_workflow(repository_reference: GithubRepositoryReference, registries: Optional[List[str]] = None) -> WorkflowVersion:
    logger.debug("Repository ref: %r", repository_reference)
    # set a reference to LifeMonitorService
    lm = LifeMonitor.get_instance()
    # set a reference to the github repo
    repo: GithubWorkflowRepository = repository_reference.repository
    logger.debug("Repository: %r", repo)

    # set reference to the github workflow registry
    github_registry: GithubWorkflowRegistry = repository_reference.event.installation.github_registry

    # normalized list of registries
    registries = __normalize_registry_identitiers__(registries)

    #
    registered_workflow = None

    # set a reference to the Gihub hosting service instance
    hosting_service: HostingService = repository_reference.hosting_service
    logger.debug("Hosting service: %r", hosting_service)

    # set the workflow version name
    workflow_version = repository_reference.branch or repository_reference.tag

    # install token for private repository access (when available)
    repo_authorization = f"token {repo.auth_token}" if repo.auth_token else None

    # search user identity
    submitter = identify_workflow_version_submitter(repository_reference)

    # set the repo link
    repo_link = f"{hosting_service.uri}/{repo.full_name}.git"
    logger.debug("Workflow RepoLink: %s", repo_link)

    # found and update the existing workflows associated with
    workflow = github_registry.find_workflow(repo.full_name)
    if workflow:
        logger.debug("Found workflow associated with the repo: %r", workflow)

        # look up the existing workflow version
        current_wv = wv = workflow.versions.get(workflow_version, None)

        # initialize registries map
        registries_map = __get_registries_map__(workflow, registries=registries)

        logger.debug("Created registries map: %r", registries_map)
        # register or update the workflow version
        if not wv:
            logger.debug("Registering workflow version on worlflow: %r ....", workflow)
            wv = lm.register_workflow(repo_link, submitter, workflow_version,
                                      workflow_uuid=workflow.uuid,
                                      name=repo.config.workflow_name, public=repo.config.public,
                                      authorization=repo_authorization)
            logger.debug("Registering workflow version on worlflow: %r .... DONE", workflow)
        else:
            logger.debug("Updating workflow version: %r...", wv)
            wv = lm.update_workflow(wv.submitter, workflow.uuid, workflow_version,
                                    name=repo.config.workflow_name,
                                    rocrate_or_link=repo_link, public=repo.config.public,
                                    authorization=repo_authorization)
            logger.debug("Updating workflow version: %r... DONE", wv)

        # register workflow on registries
        logger.debug("(old,new) workflows: (%r, %r)", current_wv, wv)
        if current_wv != wv:
            register_workflow_on_registries(github_registry, submitter, repo, wv, registries_map)
        else:
            # register workflow on new registries if any
            registries_list = [r for r in registries_map if r[0] not in wv.registry_workflow_versions] if registries_map else None
            if registries_list:
                if current_wv != wv or len(registries_list) > 0:
                    register_workflow_on_registries(github_registry, submitter, repo, wv, registries_list)
            else:
                logger.warning("Skipped registration of workflow %r on registries %r", wv, registries_list)
        # append to the list of registered workflows
        registered_workflow = wv
    # if no matches found, register a new workflow
    elif submitter:
        # register workflow version on LifeMonitor
        wv = lm.register_workflow(repo_link, submitter, workflow_version,
                                  name=repo.config.workflow_name, public=repo.config.public,
                                  authorization=repo_authorization)
        # register workflow on registries
        register_workflow_on_registries(github_registry, submitter, repo, wv, registries_map=[(_, None, []) for _ in registries])
        # append to the list of registered workflows
        registered_workflow = wv
    else:
        logger.error("Unable to register workflow version '%r': "
                     "unable to associate a LifeMonitor user to the repository submitter", workflow_version)

    # register workflow version on github registry
    if registered_workflow:
        version_settings = github_registry.add_workflow_version(registered_workflow, repo.full_name, repo.ref)
        if version_settings.notifications_enabled is None:
            version_settings.notifications_enabled = True
        github_registry.save()

    return registered_workflow


def delete_repository_workflow_version(repository_reference: GithubRepositoryReference,
                                       registries: Optional[List[str]] = None) -> Optional[Dict]:
    logger.debug("Deleting Repository ref: %r", repository_reference)
    # set a reference to LifeMonitorService
    lm = LifeMonitor.get_instance()
    # set reference to the github workflow registry
    github_registry = get_event_github_registry(repository_reference.event)
    if not github_registry:
        logger.warning("Unable to load github registry for installation %r", repository_reference.event.installation_id)
        return None

    repo_full_name = repository_reference.full_name
    logger.debug("Repository: %r", repo_full_name)

    # set a reference to the Github hosting service instance
    hosting_service: HostingService = repository_reference.hosting_service
    logger.debug("Hosting service: %r", hosting_service)

    # set the workflow version name
    workflow_version = repository_reference.branch or repository_reference.tag
    repo_ref = repository_reference.ref

    # search user identity
    submitter = identify_workflow_version_submitter(repository_reference)

    # set the repo link
    repo_link = f"{hosting_service.uri}/{repo_full_name}.git"
    logger.debug("RepoLink: %s", repo_link)

    # Registry deletion is workflow-level (not version-level):
    # only delete remotely when this is the last local version.
    w = github_registry.find_workflow(repo_full_name)
    if not w:
        logger.warning(f"No workflow associated with '{repo_full_name}' found")
    else:

        # try to find the workflow version
        wv = lm.get_user_workflow_version(submitter, w.uuid, workflow_version)
        if not wv:
            logger.warning(f"Unable to find the version {workflow_version} of workflow {w.uuid}")
            return None
        else:
            workflow_version_data = serializers.WorkflowVersionSchema(exclude=('meta', 'links')).dump(wv)
            workflow_version_data['_notification_enabled'] = get_repository_ref_notifications_enabled(
                repository_reference.event,
                repo_full_name,
                repo_ref,
                default=True,
            )

        normalized_registries = __normalize_registry_identitiers__(registries, as_strings=True)
        logger.debug("Normalized list of registries from settings: %r", normalized_registries)

        tracked_registries = sorted((wv.registry_workflow_versions or {}).keys())
        if tracked_registries:
            logger.debug(
                "Using registry associations from workflow version %s: %r",
                wv.version,
                tracked_registries,
            )
            candidate_registries = tracked_registries
        else:
            logger.warning(
                "No registry associations found on workflow version %s, falling back to settings: %r",
                wv.version,
                normalized_registries,
            )
            candidate_registries = normalized_registries

        registry_workflows_map = []
        for registry_name in candidate_registries:
            workflow_identifier = None
            versions = []

            r_wv = (wv.registry_workflow_versions or {}).get(registry_name, None)
            if r_wv:
                workflow_identifier = r_wv.identifier
                versions = [r_wv]
            elif normalized_registries:
                map_item = __get_registries_map__(w, registries=[registry_name])
                if map_item:
                    _, workflow_identifier, versions = map_item[0]

            if not workflow_identifier:
                logger.debug(
                    "Skipping registry deletion for %s@%s on '%s': missing workflow identifier",
                    repo_full_name,
                    repo_ref,
                    registry_name,
                )
                continue

            has_registry_versions_after_delete = any(
                version.version != wv.version and registry_name in (version.registry_workflow_versions or {})
                for version in w.versions.values()
            )
            if has_registry_versions_after_delete:
                logger.debug(
                    "Skipping registry deletion for %s@%s on '%s': other versions are still registered",
                    repo_full_name,
                    repo_ref,
                    registry_name,
                )
                continue

            logger.debug(
                "Deleting workflow '%s' from registry '%s' for %s@%s: no versions left after deletion",
                workflow_identifier,
                registry_name,
                repo_full_name,
                repo_ref,
            )
            registry_workflows_map.append((registry_name, workflow_identifier, versions))

        if registry_workflows_map:
            delete_workflow_from_registries(github_registry, submitter, w, registry_workflows_map)
            logger.debug("Deleting workflow %r from registries %r... DONE", w, registry_workflows_map)
        else:
            logger.debug("No remote registry workflow deletions required for %s@%s", repo_full_name, repo_ref)

        # delete workflow version from LifeMonitor
        logger.debug("Removing version '%r' of worlflow %r from LifeMonitor....", workflow_version, w)

        lm.deregister_user_workflow_version(w.uuid, workflow_version, submitter)
        logger.debug("Removing version '%r' of worlflow %r from LifeMonitor.... DONE", workflow_version, w)

        # return the deleted workflow version (serialized)
        return workflow_version_data

    return None


def register_workflow_on_registries(github_registry: GithubWorkflowRegistry, submitter: User, repo: GithubWorkflowRepository,
                                    workflow: WorkflowVersion, registries_map: List[Tuple[str, Optional[str]]]):
    result = []
    logger.debug("Registries map: %r", registries_map)
    for registry_name, workflow_identifier, _ in registries_map:
        logger.debug("Registering workflow %r on registry %r ", workflow, registry_name)
        registry: WorkflowRegistry = WorkflowRegistry.find_by_client_name(registry_name)
        logger.debug("Registry: %r", registry)
        if registry:
            result.append(register_workflow_on_registry(github_registry, submitter, repo, workflow, workflow_identifier, registry))
    return result


def register_workflow_on_registry(github_registry: GithubWorkflowRegistry, submitter: User,
                                  repo: GithubWorkflowRepository, workflow_version: WorkflowVersion,
                                  workflow_identifier: str, registry: Union[str, WorkflowRegistry, None]):
    assert isinstance(registry, str) or isinstance(registry, WorkflowRegistry), registry
    registry: WorkflowRegistry = WorkflowRegistry.find_by_client_name(registry) if isinstance(registry, str) else registry
    logger.warning("Registry: %r", registry)
    if registry:
        try:
            registered_workflow = registry.register_workflow_version(
                submitter, workflow_version.repository, external_id=workflow_identifier)
            logger.debug("Registered workflows: %r", registered_workflow)
            workflow_version.workflow.external_id = registered_workflow.identifier
            logger.debug("Adding workflow version %r to registry %r", workflow_version, registry)
            registry.add_workflow_version(workflow_version, registered_workflow.identifier, registered_workflow.latest_version, registry_workflow=registered_workflow)
            for auth in submitter.get_authorization(registry):
                auth.resources.append(workflow_version.workflow)
            workflow_version.save()
            return registered_workflow
        except Exception as e:
            logger.exception(e)
    return None


def delete_workflow_from_registries(github_registry: GithubWorkflowRegistry, submitter: User,
                                    workflow: WorkflowVersion, registries_map: List[Tuple[str, Optional[str]]]):
    result = []
    logger.debug("Registries: %r", registries_map)
    for registry_name, workflow_identifier, _ in registries_map:
        logger.debug("Processing deletion of workflow %r on registry %r", workflow_identifier, registry_name)
        if workflow_identifier:
            registry: WorkflowRegistry = WorkflowRegistry.find_by_client_name(registry_name)
            logger.debug("Registry: %r", registry)
            if registry:
                registry.client.delete_workflow(submitter, workflow_identifier)
                result.append(workflow_identifier)
    return result
