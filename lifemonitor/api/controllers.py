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

import logging
import tempfile

import connexion
import lifemonitor.exceptions as lm_exceptions
import werkzeug
from flask import Response, request, render_template
from lifemonitor.api import models, serializers
from lifemonitor.api.services import LifeMonitor
from lifemonitor.auth import (EventType, authorized, current_registry,
                              current_user)
from lifemonitor.auth import serializers as auth_serializers
from lifemonitor.auth.models import Subscription
from lifemonitor.auth.oauth2.client.models import \
    OAuthIdentityNotFoundException
from lifemonitor.cache import Timeout, cached, clear_cache
from lifemonitor.lang import messages
from lifemonitor.utils import notify_updates, notify_workflow_version_updates

# Initialize a reference to the LifeMonitor instance
lm = LifeMonitor.get_instance()

# Config a module level logger
logger = logging.getLogger(__name__)


def _row_to_dict(row):
    d = {}
    for column in row.__table__.columns:
        d[column.name] = getattr(row, column.name)
    return d


@cached(timeout=Timeout.REQUEST)
def workflow_registries_get():
    registries = lm.get_workflow_registries()
    logger.debug("registries_get. Got %s registries", len(registries))
    return serializers.ListOfWorkflowRegistriesSchema().dump(registries)


@cached(timeout=Timeout.REQUEST)
def workflow_registries_get_by_uuid(registry_uuid):
    registry = lm.get_workflow_registry_by_uuid(registry_uuid)
    logger.debug("registries_get. Got %s registry", registry)
    return serializers.WorkflowRegistrySchema().dump(registry)


@authorized
@cached(timeout=Timeout.REQUEST)
def registry_index(registry_uuid):
    if not current_user:
        return lm_exceptions.report_problem(401, "Unauthorized")
    registry = lm.get_workflow_registry_by_uuid(registry_uuid)
    if not registry:
        return lm_exceptions.report_problem(404, "Not Found",
                                            detail=messages.no_registry_found.format(registry_uuid))
    workflows = registry.get_index(current_user)
    return serializers.ListOfRegistryIndexItemsSchema().dump(workflows)


@authorized
@cached(timeout=Timeout.REQUEST)
def registry_index_workflow(registry_uuid, registry_workflow_identifier):
    if not current_user:
        return lm_exceptions.report_problem(401, "Unauthorized")
    registry = lm.get_workflow_registry_by_uuid(registry_uuid)
    if not registry:
        return lm_exceptions.report_problem(404, "Not Found",
                                            detail=messages.no_registry_found.format(registry_uuid))
    workflow = registry.get_index_workflow(current_user, registry_workflow_identifier)
    if not workflow:
        return lm_exceptions.report_problem(404, "Not Found",
                                            detail=messages.workflow_version_not_found.format(registry_workflow_identifier, 'latest'))
    return serializers.RegistryIndexItemSchema().dump(workflow)


@authorized
@cached(timeout=Timeout.REQUEST)
def workflow_registries_get_current():
    if current_registry:
        registry = current_registry
        logger.debug("registries_get. Got %s registry", registry)
        return serializers.WorkflowRegistrySchema().dump(registry)
    return lm_exceptions.report_problem(401, "Unauthorized")


@cached(timeout=Timeout.REQUEST)
def workflows_get(status=False, versions=False):
    workflows = lm.get_public_workflows()
    if current_user and not current_user.is_anonymous:
        workflows.extend(lm.get_user_workflows(current_user))
    elif current_registry:
        workflows.extend(lm.get_registry_workflows(current_registry))
    logger.debug("workflows_get. Got %s workflows (user: %s)", len(workflows), current_user)
    return serializers.ListOfWorkflows(workflow_status=status, workflow_versions=versions).dump(
        list(dict.fromkeys(workflows))
    )


def __get_workflow_version__(wf_uuid, wf_version=None) -> models.WorkflowVersion:
    try:
        wf = None
        try:
            wf = lm.get_public_workflow_version(wf_uuid, wf_version)
        except lm_exceptions.EntityNotFoundException as e:
            logger.debug(e)
        if not wf:
            if current_user and not current_registry:
                wf = lm.get_user_workflow_version(current_user, wf_uuid, wf_version)
            elif current_registry:
                wf = lm.get_registry_workflow_version(current_registry, wf_uuid, wf_version)
            else:
                raise lm_exceptions.Forbidden(detail=messages.no_user_in_session)
        if wf is None:
            raise lm_exceptions.EntityNotFoundException(
                models.WorkflowVersion,
                detail=messages.workflow_version_not_found.format(wf_uuid, wf_version))
        return wf
    except lm_exceptions.EntityNotFoundException as e:
        raise lm_exceptions.EntityNotFoundException(models.WorkflowVersion,
                                                    extra_info={"exception": str(e)},
                                                    detail=messages.workflow_version_not_found.format(wf_uuid, wf_version))
    except lm_exceptions.NotAuthorizedException as e:
        raise lm_exceptions.Forbidden(extra_info={"exception": str(e)},
                                      detail=messages.unauthorized_workflow_access.format(wf_uuid))


@cached(timeout=Timeout.REQUEST)
def workflows_get_by_id(wf_uuid, wf_version):
    response = __get_workflow_version__(wf_uuid, wf_version)
    return response if isinstance(response, Response) \
        else serializers.WorkflowVersionSchema(subscriptionsOf=[current_user]
                                               if not current_user.is_anonymous
                                               else None, rocrate_metadata=True).dump(response)


@cached(timeout=Timeout.REQUEST)
def workflows_get_latest_version_by_id(wf_uuid, previous_versions=False, ro_crate=False):
    response = __get_workflow_version__(wf_uuid, None)
    exclude = ['previous_versions'] if not previous_versions else []
    logger.debug("Previous versions: %r", exclude)
    return response if isinstance(response, Response) \
        else serializers.LatestWorkflowVersionSchema(
            exclude=exclude, rocrate_metadata=ro_crate,
            subscriptionsOf=[current_user] if not current_user.is_anonymous else None).dump(response)


@cached(timeout=Timeout.REQUEST)
def workflows_get_version_by_id(wf_uuid, wf_version, ro_crate=False):
    response = __get_workflow_version__(wf_uuid, wf_version)
    exclude = ['previous_versions']
    logger.debug("Previous versions: %r", exclude)
    return response if isinstance(response, Response) \
        else serializers.LatestWorkflowVersionSchema(
            exclude=exclude, rocrate_metadata=ro_crate,
            subscriptionsOf=[current_user] if not current_user.is_anonymous else None).dump(response)


@cached(timeout=Timeout.REQUEST)
def workflows_get_versions_by_id(wf_uuid):
    response = __get_workflow_version__(wf_uuid, None)
    return response if isinstance(response, Response) \
        else serializers.ListOfWorkflowVersions().dump(response.workflow)


@cached(timeout=Timeout.REQUEST)
def workflows_get_status(wf_uuid, version):
    response = __get_workflow_version__(wf_uuid, version)
    return response if isinstance(response, Response) \
        else serializers.WorkflowStatusSchema().dump(response)


@cached(timeout=Timeout.REQUEST)
def workflows_rocrate_metadata(wf_uuid, wf_version):
    response = __get_workflow_version__(wf_uuid, wf_version)
    if isinstance(response, Response):
        return response
    return response.crate_metadata


@cached(timeout=Timeout.WORKFLOW, client_scope=False)
def workflows_rocrate_download(wf_uuid, wf_version):
    response = __get_workflow_version__(wf_uuid, wf_version)
    if isinstance(response, Response):
        return response

    with tempfile.TemporaryDirectory() as tmpdir:
        local_zip = response.download(tmpdir)
        logger.debug("ZIP Archive: %s", local_zip)
        with open(local_zip, "rb") as f:
            return werkzeug.Response(f.read(), headers={
                'Content-Type': 'application/zip',
                'Accept': 'application/json',
                'Access-Control-Allow-Credentials': 'true',
                'Access-Control-Allow-Origin': '*',
                'Content-Disposition': f'attachment; filename=rocrate_{response.workflow.uuid}_v{response.version}.zip'
            }, direct_passthrough=False)


@authorized
@cached(timeout=Timeout.REQUEST)
def registry_workflows_get(status=False, versions=False):
    workflows = lm.get_registry_workflows(current_registry)
    logger.debug("workflows_get. Got %s workflows (registry: %s)", len(workflows), current_registry)
    return serializers.ListOfWorkflows(workflow_status=status, workflow_versions=versions).dump(workflows)


@authorized
def registry_workflows_post(body):
    if not current_registry:
        return lm_exceptions.report_problem(401, "Unauthorized", detail=messages.no_registry_found)
    clear_cache()
    return workflows_post(body)


@authorized
@cached(timeout=Timeout.REQUEST)
def registry_user_workflows_get(user_id, status=False, versions=False):
    if not current_registry:
        return lm_exceptions.report_problem(401, "Unauthorized", detail=messages.no_registry_found)
    try:
        identity = lm.find_registry_user_identity(current_registry, external_id=user_id)
        workflows = lm.get_user_registry_workflows(identity.user, current_registry)
        logger.debug("registry_user_workflows_get. Got %s workflows (user: %s)", len(workflows), current_user)
        return serializers.ListOfWorkflows(workflow_status=status, workflow_versions=versions).dump(workflows)
    except OAuthIdentityNotFoundException:
        return lm_exceptions.report_problem(401, "Unauthorized",
                                            detail=messages.no_user_oauth_identity_on_registry
                                            .format(user_id, current_registry.name))


@authorized
def registry_user_workflows_post(user_id, body):
    if not current_registry:
        return lm_exceptions.report_problem(401, "Unauthorized", detail=messages.no_registry_found)
    clear_cache()
    return workflows_post(body, _submitter_id=user_id)


@authorized
@cached(timeout=Timeout.REQUEST)
def user_workflows_get(status=False, subscriptions=False, versions=False):
    if not current_user or current_user.is_anonymous:
        return lm_exceptions.report_problem(401, "Unauthorized", detail=messages.no_user_in_session)
    workflows = lm.get_user_workflows(current_user, include_subscriptions=subscriptions)
    logger.debug("user_workflows_get. Got %s workflows (user: %s)", len(workflows), current_user)
    return serializers.ListOfWorkflows(workflow_status=status,
                                       workflow_versions=versions,
                                       subscriptionsOf=[current_user]
                                       if subscriptions else None).dump(workflows)


@authorized
def user_workflows_post(body):
    if not current_user or current_user.is_anonymous:
        return lm_exceptions.report_problem(401, "Unauthorized", detail=messages.no_user_in_session)
    clear_cache()
    return workflows_post(body)


@authorized
def user_workflow_subscribe(wf_uuid):
    response = __get_workflow_version__(wf_uuid)
    # if isinstance(response, Response):
    #     return response
    subscribed = current_user.is_subscribed_to(response.workflow)
    subscription = lm.subscribe_user_resource(current_user, response.workflow)
    logger.debug("Created new subscription: %r", subscription)
    clear_cache()
    if not subscribed:
        return auth_serializers.SubscriptionSchema(exclude=('meta', 'links')).dump(subscription), 201
    else:
        return connexion.NoContent, 204


@authorized
def user_workflow_subscribe_events(wf_uuid, body):
    workflow_version = __get_workflow_version__(wf_uuid)

    if body is None or not isinstance(body, list):
        return lm_exceptions.report_problem(400, "Bad request",
                                            detail=messages.invalid_event_type.format(EventType.all_names()))
    try:
        events = EventType.from_strings(body)
        if isinstance(workflow_version, Response):
            return workflow_version
        subscription: Subscription = current_user.get_subscription(workflow_version.workflow)
        if subscription and subscription.events == events:
            return connexion.NoContent, 204
        subscription = lm.subscribe_user_resource(current_user, workflow_version.workflow, events=events)
        logger.debug("Updated subscription events: %r", subscription)
        clear_cache()
        return auth_serializers.SubscriptionSchema(exclude=('meta', 'links')).dump(subscription), 201
    except ValueError as e:
        logger.debug(e)
        return lm_exceptions.report_problem(400, "Bad request",
                                            detail=messages.invalid_event_type.format(EventType.all_names()))
    except Exception as e:
        logger.debug(e)
        return lm_exceptions.report_problem_from_exception(e)


@authorized
def user_workflow_unsubscribe(wf_uuid):
    response = __get_workflow_version__(wf_uuid)
    # if isinstance(response, Response):
    #     return response
    subscription = lm.unsubscribe_user_resource(current_user, response.workflow)
    logger.debug("Delete subscription: %r", subscription)
    clear_cache()
    return connexion.NoContent, 204


@authorized
@cached(timeout=Timeout.REQUEST)
def user_registry_workflows_get(registry_uuid, status=False, versions=False):
    if not current_user or current_user.is_anonymous:
        return lm_exceptions.report_problem(401, "Unauthorized", detail=messages.no_user_in_session)
    logger.debug("Registry UUID: %r", registry_uuid)
    try:
        registry = lm.get_workflow_registry_by_uuid(registry_uuid)
        workflows = lm.get_user_registry_workflows(current_user, registry)
        logger.debug("workflows_get. Got %s workflows (user: %s)", len(workflows), current_user)
        return serializers.ListOfWorkflows(workflow_status=status, workflow_versions=versions).dump(workflows)
    except lm_exceptions.EntityNotFoundException:
        return lm_exceptions.report_problem(404, "Not Found",
                                            detail=messages.no_registry_found.format(registry_uuid))


@authorized
def user_registry_workflows_post(registry_uuid, body):
    if not current_user or current_user.is_anonymous:
        return lm_exceptions.report_problem(401, "Unauthorized", detail=messages.no_user_in_session)
    try:
        registry = lm.get_workflow_registry_by_uuid(registry_uuid)
        clear_cache()
        return workflows_post(body, _registry=registry)
    except lm_exceptions.EntityNotFoundException:
        return lm_exceptions.report_problem(404, "Not Found",
                                            detail=messages.no_registry_found.format(registry_uuid))


def __check_submitter_and_registry__(body, _registry=None, _submitter_id=None, _check_identifier=True):
    registry = _registry or current_registry._get_current_object()
    if registry and 'registry' in body:
        raise lm_exceptions.BadRequestException(detail=messages.unexpected_registry_uri)
        # return lm_exceptions.report_problem(400, "Bad request",
        #                                     detail=messages.unexpected_registry_uri)
    if not registry and 'registry' in body:
        registry_ref = body.get('registry', None)
        try:
            registry = lm.get_workflow_registry_by_generic_reference(registry_ref)
        except lm_exceptions.EntityNotFoundException:
            raise lm_exceptions.EntityNotFoundException(
                models.WorkflowRegistry, entity_id=registry_ref,
                detail=messages.no_registry_found.format(registry_ref))
            # return lm_exceptions.report_problem(404, "Not Found",
            #                                     detail=messages.no_registry_found.format(registry_ref))
    if registry and _check_identifier:
        # at least one between 'uuid' or 'identifier' must be provided to
        # associate this workflow record with its identity in the registry
        if not body.get('uuid', None) and not body.get('identifier', None):
            # return lm_exceptions.report_problem(400, "Bad Request", extra_info={"missing input": "uuid or identifier"},
            #                                     detail=messages.input_data_missing)
            raise lm_exceptions.BadRequestException(detail=messages.input_data_missing,
                                                    extra_info={"missing input": "uuid or identifier"})

    submitter = current_user if current_user and not current_user.is_anonymous else None
    if not submitter:
        try:
            user_id = body.get('user_id', current_user.id if current_user else None)
            if user_id:
                submitter = lm.get_user_by_id(user_id)
            if not submitter:
                submitter_id = body.get('submitter_id', _submitter_id)
                if submitter_id:
                    # Try to find the identity of the submitter
                    identity = lm.find_registry_user_identity(registry,
                                                              internal_id=user_id,
                                                              external_id=submitter_id)
                    submitter = identity.user
        except KeyError:
            # return lm_exceptions.report_problem(400, "Bad request",
            #                                     detail=messages.no_submitter_id_provided)
            raise lm_exceptions.BadRequestException(detail=messages.no_submitter_id_provided)
        except OAuthIdentityNotFoundException:
            # return lm_exceptions.report_problem(401, "Unauthorized",
            #                                     detail=messages.no_user_oauth_identity_on_registry
            #                                     .format(submitter_id or current_user.id, registry.name))
            raise lm_exceptions.NotAuthorizedException(
                detail=messages.no_user_oauth_identity_on_registry
                .format(submitter_id or current_user.id, registry.name)
            )
    return registry, submitter


def workflows_post(body, _registry=None, _submitter_id=None,
                   async_processing: bool | None = None, job: Job = None):
    logger.warning("The current body: %r", body)
    # check if there exists a submitter and/or a registry in the current request
    registry, submitter = __check_submitter_and_registry__(body, _registry, _submitter_id)
    # extract roc_link or rocrate from the request
    roc_link = body.get('roc_link', None)
    encoded_rocrate = body.get('rocrate', None)
    if not registry and not roc_link and not encoded_rocrate:
        return lm_exceptions.report_problem(400, "Bad Request", extra_info={"missing input": "roc_link OR rocrate"},
                                            detail=messages.input_data_missing)

    # check whether to handle the registration asynchronously
    async_processing = body.get('async', False) if async_processing is None else async_processing
    if async_processing:
        # collect registration data
        registration_data = {
            "submitter_id": submitter.id,
            "user_id": submitter.id,
            "version": body['version'],
            "uuid": body.get('uuid', None),
            "identifier": body.get('identifier', None),
            "name": body.get('name', None),
            "authorization": body.get('authorization', None),
            "public": body.get('public', False)
        }
        if roc_link:
            registration_data['roc_link'] = roc_link
        if encoded_rocrate:
            registration_data['rocrate'] = encoded_rocrate
        if registry:
            registration_data["registry"] = registry.name
        # create async Job
        job = Job(job_type='workflow_registration',  # job_name='register_workflow',
                  status='waiting',
                  listening_rooms=[str(registration_data['submitter_id'])])
        job.update_data({
            'data': registration_data
        })
        job.save()
        job.submit(current_app, as_job_name='register_workflow')
        return redirect(f'/jobs/status/{job.id}', code=302)

    # register workflow through the 'lm' service
    try:
        w = lm.register_workflow(
            rocrate_or_link=roc_link or encoded_rocrate,
            workflow_submitter=submitter,
            workflow_version=body['version'],
            workflow_uuid=body.get('uuid', None),
            workflow_identifier=body.get('identifier', None),
            workflow_registry=registry,
            name=body.get('name', None),
            authorization=body.get('authorization', None),
            public=body.get('public', False),
            job=job
        )
        logger.debug("workflows_post. Created workflow '%s' (ver.%s)", w.uuid, w.version)
        clear_cache()
        notify_workflow_version_updates([w], type='sync', delay=2)
        return {'uuid': str(w.workflow.uuid), 'wf_version': w.version, 'name': w.name}, 201
    except KeyError as e:
        return lm_exceptions.report_problem(400, "Bad Request", extra_info={"exception": str(e)},
                                            detail=messages.input_data_missing)
    except lm_exceptions.DownloadException as e:
        return lm_exceptions.report_problem(400, "Bad Request", extra_info={"exception": str(e)},
                                            detail=messages.invalid_ro_crate)
    except lm_exceptions.NotValidROCrateException as e:
        return lm_exceptions.report_problem(400, "Bad Request", extra_info={"exception": str(e)},
                                            detail=f"{messages.invalid_ro_crate}: {e.detail}")
    except lm_exceptions.NotAuthorizedException as e:
        return lm_exceptions.report_problem(403, "Forbidden", extra_info={"exception": str(e)},
                                            detail=messages.not_authorized_registry_access.format(registry.name)
                                            if registry else messages.not_authorized_workflow_access)
    except lm_exceptions.WorkflowVersionConflictException:
        return lm_exceptions.report_problem(409, "Workflow version conflict",
                                            detail=messages.workflow_version_conflict
                                            .format(body.get('uuid', None) or body.get('identifier', None),
                                                    body['version']))
    except lm_exceptions.LifeMonitorException:
        # Catch and re-raise to avoid the last catch-all exception handler
        raise
    except Exception as e:
        logger.exception(e)
        raise lm_exceptions.LifeMonitorException(title="Internal Error", detail=str(e))


@authorized
def workflows_put(wf_uuid, body):
    logger.debug(f"PUT called for workflow {wf_uuid} (basic info)")
    # get a reference to the workflow version to be updated
    workflow_version = __get_workflow_version__(wf_uuid)
    # update basic information aboud the specified workflow
    workflow_version.workflow.name = body.get('name', workflow_version.workflow.name)
    workflow_version.workflow.public = body.get('public', workflow_version.workflow.public)
    workflow_version.workflow.save()
    clear_cache()
    notify_workflow_version_updates([workflow_version], type='sync')
    return connexion.NoContent, 204


@authorized
def workflows_version_put(wf_uuid, wf_version, body):
    logger.debug(f"PUT called for workflow {wf_uuid} (version {wf_version})")
    # get a reference to the workflow version to be updated
    workflow_version = __get_workflow_version__(wf_uuid, wf_version)
    # check if there exists a submitter and/or a registry in the current request
    registry, submitter = __check_submitter_and_registry__(body, _check_identifier=False)
    # registry workflows cannot be updated through roc_link or rocrate
    # (roc_link and rocrate will be ignored by the 'lm' service)
    rocrate_or_link = body.get('roc_link', None) or body.get('rocrate', None)
    if len(workflow_version.registries) > 0 and rocrate_or_link is not None:
        raise lm_exceptions.Forbidden(detail=messages.forbidden_roclink_or_rocrate_for_registry_workflows)
    # perform the update through the service
    try:
        updated_workflow_version = lm.update_workflow(
            submitter,
            wf_uuid, workflow_version.version,
            name=body.get('name', workflow_version.workflow.name),
            new_version_label=body.get('version', None),
            public=body.get('public', workflow_version.workflow.public),
            rocrate_or_link=rocrate_or_link,
            authorization=body.get('authorization', None)
        )
        clear_cache()
        if updated_workflow_version.uuid != workflow_version.uuid:
            return {'uuid': str(updated_workflow_version.workflow.uuid),
                    'wf_version': updated_workflow_version.version,
                    'name': updated_workflow_version.name}, 201
        return connexion.NoContent, 204

    except KeyError as e:
        return lm_exceptions.report_problem(400, "Bad Request", extra_info={"exception": str(e)},
                                            detail=messages.input_data_missing)
    except lm_exceptions.DownloadException as e:
        return lm_exceptions.report_problem(400, "Bad Request", extra_info={"exception": str(e)},
                                            detail=messages.invalid_ro_crate)
    except lm_exceptions.NotValidROCrateException as e:
        return lm_exceptions.report_problem(400, "Bad Request", extra_info={"exception": str(e)},
                                            detail=messages.invalid_ro_crate)
    except lm_exceptions.NotAuthorizedException as e:
        return lm_exceptions.report_problem(403, "Forbidden", extra_info={"exception": str(e)},
                                            detail=messages.not_authorized_registry_access.format(registry.name)
                                            if registry else messages.not_authorized_workflow_access)
    except lm_exceptions.LifeMonitorException:
        # Catch and re-raise to avoid the last catch-all exception handler
        raise
    except Exception as e:
        logger.exception(e)
        raise lm_exceptions.LifeMonitorException(title="Internal Error", detail=str(e))


@authorized
def workflows_delete_version(wf_uuid, wf_version):
    try:
        # get a reference to the workflow version to be updated
        workflow_version = __get_workflow_version__(wf_uuid, wf_version=wf_version)
        if current_user and not current_user.is_anonymous:
            lm.deregister_user_workflow_version(wf_uuid, wf_version, current_user)
        elif current_registry:
            lm.deregister_registry_workflow_version(wf_uuid, wf_version, current_registry)
        else:
            return lm_exceptions.report_problem(403, "Forbidden",
                                                detail=messages.no_user_in_session)
        clear_cache()
        notify_workflow_version_updates([workflow_version], type='delete')
        return connexion.NoContent, 204
    except OAuthIdentityNotFoundException as e:
        return lm_exceptions.report_problem(401, "Unauthorized", extra_info={"exception": str(e)})
    except lm_exceptions.EntityNotFoundException as e:
        return lm_exceptions.report_problem(404, "Not Found", extra_info={"exception": str(e.detail)},
                                            detail=messages.workflow_version_not_found.format(wf_uuid, wf_version))
    except lm_exceptions.NotAuthorizedException as e:
        return lm_exceptions.report_problem(403, "Forbidden", extra_info={"exception": str(e)})
    except Exception as e:
        raise lm_exceptions.LifeMonitorException(title="Internal Error", detail=str(e))


@authorized
def workflows_delete(wf_uuid):
    try:
        if current_user and not current_user.is_anonymous:
            lm.deregister_user_workflow(wf_uuid, current_user)
        elif current_registry:
            lm.deregister_registry_workflow(wf_uuid, current_registry)
        else:
            return lm_exceptions.report_problem(403, "Forbidden",
                                                detail=messages.no_user_in_session)
        clear_cache()
        notify_updates([{'uuid': wf_uuid}], type='delete')
        return connexion.NoContent, 204
    except OAuthIdentityNotFoundException as e:
        return lm_exceptions.report_problem(401, "Unauthorized", extra_info={"exception": str(e)})
    except lm_exceptions.EntityNotFoundException as e:
        return lm_exceptions.report_problem(404, "Not Found", extra_info={"exception": str(e.detail)},
                                            detail=messages.workflow_version_not_found.format(wf_uuid))
    except lm_exceptions.NotAuthorizedException as e:
        return lm_exceptions.report_problem(403, "Forbidden", extra_info={"exception": str(e)})
    except Exception as e:
        raise lm_exceptions.LifeMonitorException(title="Internal Error", detail=str(e))


@cached(timeout=Timeout.REQUEST)
def workflows_get_issue_types():
    return serializers.ListOfWorkflowIssueTypesSchema().dump(models.WorkflowRepositoryIssue.all())


@cached(timeout=Timeout.REQUEST)
def workflows_get_issue_types_as_html(back=None):
    return Response(
        render_template(
            "api/issues.j2", back_param=back,
            issues=serializers.ListOfWorkflowIssueTypesSchema().dump(models.WorkflowRepositoryIssue.all())['items']),
        mimetype="text/html", status=200)


@cached(timeout=Timeout.REQUEST)
def workflows_get_suites(wf_uuid, version='latest', status: bool = False, latest_builds: bool = False):
    workflow_version = __get_workflow_version__(wf_uuid, version)
    logger.debug("GET suites of workflow version: %r", workflow_version)
    return serializers.ListOfSuites(
        status=status, latest_builds=latest_builds
    ).dump(workflow_version.test_suites)


def _get_suite_or_problem(suite_uuid):
    try:
        suite = lm.get_suite(suite_uuid)
        if not suite:
            return lm_exceptions.report_problem(404, "Not Found",
                                                detail=messages.suite_not_found.format(suite_uuid))

        response = __get_workflow_version__(suite.workflow_version.workflow.uuid,
                                            suite.workflow_version.version)
        if isinstance(response, Response):
            if response.status_code == 404:
                return lm_exceptions.report_problem(500, "Internal Error",
                                                    extra_info={"reason": response.get_json()['detail']})
            details_message = ""
            if current_user and not current_user.is_anonymous:
                details_message = messages.unauthorized_user_suite_access\
                    .format(current_user.username, suite_uuid)
            elif current_registry:
                details_message = messages.unauthorized_registry_suite_access\
                    .format(current_registry.name, suite_uuid)
            return lm_exceptions.report_problem(403, "Forbidden",
                                                detail=details_message,
                                                extra_info={"reason": response.get_json()['detail']})
        return suite
    except lm_exceptions.EntityNotFoundException:
        return lm_exceptions.report_problem(404, "Not Found", detail=messages.suite_not_found.format(suite_uuid))


@cached(timeout=Timeout.REQUEST)
def suites_get_by_uuid(suite_uuid, status: bool = False, latest_builds: bool = False):
    response = _get_suite_or_problem(suite_uuid)
    return response if isinstance(response, Response) \
        else serializers.SuiteSchema(status=status, latest_builds=latest_builds).dump(response)


@cached(timeout=Timeout.REQUEST)
def suites_get_status(suite_uuid):
    response = _get_suite_or_problem(suite_uuid)
    return response if isinstance(response, Response) \
        else serializers.SuiteStatusSchema().dump(response)


@cached(timeout=Timeout.REQUEST)
def suites_get_instances(suite_uuid):
    response = _get_suite_or_problem(suite_uuid)
    return response if isinstance(response, Response) \
        else serializers.ListOfTestInstancesSchema().dump(response.test_instances)


@authorized
def suites_post(wf_uuid, wf_version, body):
    # A the moment, this controller is not linked to the API specs
    if current_user and not current_user.is_anonymous:
        submitter = current_user
    if submitter is None:
        return "No valid submitter found", 404
    suite = lm.register_test_suite(
        workflow_uuid=wf_uuid,
        workflow_version=wf_version,
        workflow_submitter=submitter,
        test_suite_metadata=body['test_suite_metadata']
    )
    logger.debug("suite_post. Created test suite with name '%s'", suite.uuid)
    return {'wf_uuid': str(suite.uuid)}, 201


@authorized
def suites_put(suite_uuid, body):
    try:
        suite = _get_suite_or_problem(suite_uuid)
        if isinstance(suite, Response):
            return suite
        suite.name = body.get('name', suite.name)
        suite.save()
        clear_cache()
        logger.debug("Suite %r updated", suite_uuid)
        return connexion.NoContent, 204
    except Exception as e:
        return lm_exceptions.report_problem(500, "Internal Error", extra_info={"exception": str(e)},
                                            detail=messages.unable_to_delete_suite.format(suite_uuid))


@authorized
def suites_delete(suite_uuid):
    try:
        response = _get_suite_or_problem(suite_uuid)
        if isinstance(response, Response):
            return response
        if lm.deregister_test_suite(response) == suite_uuid:
            return connexion.NoContent, 204
        return lm_exceptions.report_problem(500, "Internal Error",
                                            detail=messages.unable_to_delete_suite.format(suite_uuid))
    except Exception as e:
        return lm_exceptions.report_problem(500, "Internal Error", extra_info={"exception": str(e)},
                                            detail=messages.unable_to_delete_suite.format(suite_uuid))


@authorized
def suites_post_instance(suite_uuid):
    try:
        response = _get_suite_or_problem(suite_uuid)
        if isinstance(response, Response):
            return response
        # data as JSON
        data = request.get_json()
        # notify that 'managed' are not supported
        if data['managed'] is True:
            return lm_exceptions.report_problem(501, "Not implemented yet",
                                                detail="Only unmanaged test instances are supported!")
        submitter = current_user if current_user and not current_user.is_anonymous else None
        test_instance = lm.register_test_instance(response, submitter,
                                                  data['managed'],
                                                  data['name'],
                                                  data['service']['type'],
                                                  data['service']['url'],
                                                  data['resource'])
        clear_cache()
        return {'uuid': str(test_instance.uuid)}, 201
    except KeyError as e:
        return lm_exceptions.report_problem(400, "Bad Request", extra_info={"exception": str(e)},
                                            detail=messages.input_data_missing)
    except lm_exceptions.EntityNotFoundException:
        return "Invalid ID", 400


def _get_instances_or_problem(instance_uuid):
    try:
        instance = lm.get_test_instance(instance_uuid)
        if not instance:
            return lm_exceptions.report_problem(404, "Not Found",
                                                detail=messages.instance_not_found.format(instance_uuid))
        response = _get_suite_or_problem(instance.test_suite.uuid)
        if isinstance(response, Response):
            logger.debug("Data: %r", response.get_json())
            if response.status_code == 404:
                return lm_exceptions.report_problem(500, "Internal Error",
                                                    extra_info={"reason": response.get_json()['detail']})
            details_message = ""
            if current_user and not current_user.is_anonymous:
                details_message = messages.unauthorized_user_instance_access\
                    .format(current_user.username, instance_uuid)
            elif current_registry:
                details_message = messages.unauthorized_registry_instance_access\
                    .format(current_registry.name, instance_uuid)
            return lm_exceptions.report_problem(403, "Forbidden", detail=details_message,
                                                extra_info={"reason": response.get_json()})
        return instance
    except lm_exceptions.EntityNotFoundException:
        return lm_exceptions.report_problem(404, "Not Found",
                                            detail=messages.instance_not_found.format(instance_uuid))


@cached(timeout=Timeout.REQUEST)
def instances_get_by_id(instance_uuid):
    response = _get_instances_or_problem(instance_uuid)
    return response if isinstance(response, Response) \
        else serializers.TestInstanceSchema().dump(response)


@authorized
def instances_put(instance_uuid, body):
    try:
        instance = _get_instances_or_problem(instance_uuid)
        if isinstance(instance, Response):
            return instance
        instance.name = body.get('name', instance.name)
        instance.save()
        clear_cache()
        logger.debug("Instance %r updated", instance_uuid)
        return connexion.NoContent, 204
    except Exception as e:
        return lm_exceptions.report_problem(500, "Internal Error", extra_info={"exception": str(e)},
                                            detail=messages.unable_to_delete_suite.format(instance_uuid))


@authorized
def instances_delete_by_id(instance_uuid):
    try:
        response = _get_instances_or_problem(instance_uuid)
        if isinstance(response, Response):
            return response
        lm.deregister_test_instance(response)
        clear_cache()
        return connexion.NoContent, 204
    except OAuthIdentityNotFoundException as e:
        return lm_exceptions.report_problem(401, "Unauthorized", extra_info={"exception": str(e)})
    except lm_exceptions.EntityNotFoundException as e:
        return lm_exceptions.report_problem(404, "Not Found", extra_info={"exception": str(e.detail)},
                                            detail=messages.instance_not_found.format(instance_uuid))
    except lm_exceptions.NotAuthorizedException as e:
        return lm_exceptions.report_problem(403, "Forbidden", extra_info={"exception": str(e)})
    except Exception as e:
        raise lm_exceptions.LifeMonitorException(title="Internal Error", detail=str(e))


@cached(timeout=Timeout.REQUEST)
def instances_get_builds(instance_uuid, limit):
    response = _get_instances_or_problem(instance_uuid)
    logger.info("Number of builds to load: %r", limit)
    return response if isinstance(response, Response) \
        else serializers.ListOfTestBuildsSchema().dump(response.get_test_builds(limit=limit))


@cached(timeout=Timeout.REQUEST)
def instances_builds_get_by_id(instance_uuid, build_id):
    response = _get_instances_or_problem(instance_uuid)
    if isinstance(response, Response):
        return response
    try:
        build = response.get_test_build(build_id)
        logger.debug("The test build: %r", build)
        if build:
            return serializers.BuildSummarySchema().dump(build)
        else:
            return lm_exceptions\
                .report_problem(404, "Not Found",
                                detail=messages.instance_build_not_found.format(build_id, instance_uuid))
    except lm_exceptions.EntityNotFoundException:
        return lm_exceptions\
            .report_problem(404, "Not Found",
                            detail=messages.instance_build_not_found.format(build_id, instance_uuid))
    except lm_exceptions.RateLimitExceededException as e:
        return lm_exceptions.report_problem(403, e.title, detail=e.detail)
    except lm_exceptions.BadRequestException as e:
        return lm_exceptions.report_problem(400, e.title, detail=e.detail)
    except Exception as e:
        return lm_exceptions.report_problem(500, "Internal Error", extra_info={"exception": str(e)})


@authorized
def instances_builds_get_logs(instance_uuid, build_id, offset_bytes=0, limit_bytes=131072):
    if not isinstance(offset_bytes, int) or offset_bytes < 0:
        return lm_exceptions.report_problem(400, "Bad Request", detail=messages.invalid_log_offset)
    if not isinstance(limit_bytes, int) or limit_bytes < 0:
        return lm_exceptions.report_problem(400, "Bad Request", detail=messages.invalid_log_limit)
    response = _get_instances_or_problem(instance_uuid)
    if isinstance(response, Response):
        return response
    try:
        build = response.get_test_build(build_id)
        logger.debug("offset = %r, limit = %r", offset_bytes, limit_bytes)
        if build:
            return build.get_output(offset_bytes=offset_bytes, limit_bytes=limit_bytes)
        return lm_exceptions\
            .report_problem(404, "Not Found",
                            detail=messages.instance_build_not_found.format(build_id, instance_uuid))
    except lm_exceptions.EntityNotFoundException:
        return lm_exceptions\
            .report_problem(404, "Not Found",
                            detail=messages.instance_build_not_found.format(build_id, instance_uuid))
    except lm_exceptions.RateLimitExceededException as e:
        return lm_exceptions.report_problem(403, e.title, detail=e.detail)
    except ValueError as e:
        return lm_exceptions.report_problem(400, "Bad Request", detail=str(e))
    except Exception as e:
        logger.exception(e)
        return lm_exceptions.report_problem(500, "Internal Error", extra_info={"exception": str(e)})
