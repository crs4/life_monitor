#!/usr/bin/env python3
import logging

import connexion
import lifemonitor.exceptions as lm_exceptions
import werkzeug.exceptions as http_exceptions
from flask import Response, g
from lifemonitor.api import serializers
from lifemonitor.api.services import LifeMonitor
from lifemonitor.auth import authorized, current_registry, current_user
from lifemonitor.auth.oauth2.client.models import \
    OAuthIdentityNotFoundException
from lifemonitor.lang import messages

# Initialize a reference to the LifeMonitor instance
lm = LifeMonitor.get_instance()

# Config a module level logger
logger = logging.getLogger(__name__)


def _row_to_dict(row):
    d = {}
    for column in row.__table__.columns:
        d[column.name] = getattr(row, column.name)
    return d


# @authorized
def workflow_registries_get():
    registries = lm.get_workflow_registries()
    logger.debug("registries_get. Got %s registries", len(registries))
    return serializers.WorkflowRegistrySchema().dump(registries, many=True)


# @authorized
def workflow_registries_get_by_uuid(registry_uuid):
    registry = lm.get_workflow_registry_by_uuid(registry_uuid)
    logger.debug("registries_get. Got %s registry", registry)
    return serializers.WorkflowRegistrySchema().dump(registry)


@authorized
def workflow_registries_get_current():
    if current_registry:
        registry = current_registry
        logger.debug("registries_get. Got %s registry", registry)
        return serializers.WorkflowRegistrySchema().dump(registry)
    return lm_exceptions.report_problem(401, "Unauthorized")


@authorized
def workflows_post(body):
    registry = current_registry
    if registry and 'registry_uri' in body:
        return lm_exceptions.report_problem(400, "Bad request",
                                            detail=messages.unexpected_registry_uri)
    if not registry and 'registry_uri' in body:
        registry_uri = body.get('registry_uri', None)
        try:
            registry = lm.get_workflow_registry_by_uri(registry_uri)
        except lm_exceptions.EntityNotFoundException:
            return lm_exceptions.report_problem(404, "Not Found",
                                                detail=messages.no_registry_found.format(registry_uri))
    submitter = current_user
    if not current_user or current_user.is_anonymous:  # the client is a registry
        try:
            submitter_id = body['submitter_id']
            # Try to find the identity of the submitter
            identity = lm.find_registry_user_identity(registry,
                                                      internal_id=current_user.id,
                                                      external_id=submitter_id)
            submitter = identity.user
        except KeyError:
            return lm_exceptions.report_problem(400, "Bad request",
                                                detail=messages.no_submitter_id_provided)
        except OAuthIdentityNotFoundException:
            return lm_exceptions.report_problem(401, "Unauthorized",
                                                detail=messages.no_user_oauth_identity_on_registry
                                                .format(submitter_id or current_user.id, registry.name))
    try:
        w = lm.register_workflow(
            workflow_submitter=submitter,
            workflow_uuid=body['uuid'],
            workflow_version=body['version'],
            roc_link=body['roc_link'],
            workflow_registry=registry,
            name=body.get('name', None)
        )
        logger.debug("workflows_post. Created workflow '%s' (ver.%s)", w.uuid, w.version)
        return {'wf_uuid': str(w.uuid), 'wf_version': w.version}, 201
    except KeyError as e:
        return lm_exceptions.report_problem(400, "Bad Request", extra_info={"exception": str(e)},
                                            detail=messages.input_data_missing)
    except lm_exceptions.NotValidROCrateException as e:
        return lm_exceptions.report_problem(400, "Bad Request", extra_info={"exception": str(e)},
                                            detail=messages.invalid_ro_crate)
    except lm_exceptions.NotAuthorizedException as e:
        return lm_exceptions.report_problem(403, "Forbidden", extra_info={"exception": str(e)},
                                            detail=messages.not_authorized_registry_access
                                            .format(registry.name))
    except lm_exceptions.WorkflowVersionConflictException:
        raise lm_exceptions.report_problem(409, "Workflow version conflict",
                                           detail=messages.workflow_version_conflict.format(body['uuid'], body['version']))
    except Exception as e:
        logger.exception(e)
        raise lm_exceptions.LifeMonitorException(title="Internal Error", detail=str(e))


@authorized
def workflows_put(wf_uuid, wf_version, body):
    # TODO: to be implemented
    logger.debug("PUT called for workflow (%s,%s)", wf_uuid, wf_version)
    # try:
    #     wf = model.WorkflowVersion.query.get(wf_id)
    # except sqlalchemy.exc.DataError:
    #     return "Invalid ID", 400
    # wf.name = body['name']
    # db.session.commit()
    # return connexion.NoContent, 200
    raise http_exceptions.NotImplemented()


@authorized
def workflows_delete(wf_uuid, wf_version):
    try:
        if current_user and not current_user.is_anonymous:
            lm.deregister_user_workflow(wf_uuid, wf_version, current_user)
        elif current_registry:
            lm.deregister_registry_workflow(wf_uuid, wf_version, current_registry)
        else:
            return lm_exceptions.report_problem(403, "Forbidden",
                                                detail=messages.no_user_in_session)
        return connexion.NoContent, 204
    except lm_exceptions.EntityNotFoundException as e:
        return lm_exceptions.report_problem(404, "Not Found", extra_info={"exception": str(e.detail)},
                                            detail=messages.workflow_not_found.format(wf_uuid, wf_version))
    except OAuthIdentityNotFoundException as e:
        return lm_exceptions.report_problem(401, "Unauthorized", extra_info={"exception": str(e)})
    except lm_exceptions.NotAuthorizedException as e:
        return lm_exceptions.report_problem(403, "Forbidden", extra_info={"exception": str(e)})
    except Exception as e:
        raise lm_exceptions.LifeMonitorException(title="Internal Error", detail=str(e))


@authorized
def workflows_get():
    workflows = []
    if current_user and not current_user.is_anonymous:
        workflows.extend(lm.get_user_workflows(current_user))
    elif current_registry:
        workflows.extend(lm.get_registry_workflows(current_registry))
    else:
        return lm_exceptions.report_problem(401, "Unauthorized", detail=messages.no_user_in_session)
    logger.debug("workflows_get. Got %s workflows (user: %s)", len(workflows), current_user)
    return serializers.WorkflowSchema().dump(workflows, many=True)


def _get_workflow_or_problem(wf_uuid, wf_version):
    try:
        wf = None
        if current_user and not current_user.is_anonymous:
            wf = lm.get_user_workflow_version(current_user, wf_uuid, wf_version)
        elif current_registry:
            wf = lm.get_registry_workflow_version(current_registry, wf_uuid, wf_version)
        else:
            return lm_exceptions.report_problem(403, "Forbidden",
                                                detail=messages.no_user_in_session)
        if wf is None:
            return lm_exceptions.report_problem(404, "Not Found",
                                                detail=messages.workflow_not_found.format(wf_uuid, wf_version))
        return wf
    except lm_exceptions.EntityNotFoundException as e:
        return lm_exceptions.report_problem(404, "Not Found", extra_info={"exception": str(e)},
                                            detail=messages.workflow_not_found.format(wf_uuid, wf_version))
    except lm_exceptions.NotAuthorizedException as e:
        return lm_exceptions.report_problem(403, "Forbidden", extra_info={"exception": str(e)},
                                            detail=messages.unauthorized_workflow_access.format(wf_uuid))


@authorized
def workflows_get_by_id(wf_uuid, wf_version):
    response = _get_workflow_or_problem(wf_uuid, wf_version)
    return response if isinstance(response, Response) \
        else serializers.WorkflowVersionDetailsSchema().dump(response)


@authorized
def workflows_get_latest_version_by_id(wf_uuid):
    response = _get_workflow_or_problem(wf_uuid, None)
    return response if isinstance(response, Response) \
        else serializers.LatestWorkflowSchema().dump(response)


@authorized
def workflows_get_status(wf_uuid, wf_version):
    response = _get_workflow_or_problem(wf_uuid, wf_version)
    return response if isinstance(response, Response) \
        else serializers.WorkflowStatusSchema().dump(response.status)


@authorized
def workflows_get_suites(wf_uuid, wf_version):
    response = _get_workflow_or_problem(wf_uuid, wf_version)
    return response if isinstance(response, Response) \
        else serializers.SuiteSchema().dump(response.test_suites, many=True)


def _get_suite_or_problem(suite_uuid):
    try:
        suite = lm.get_suite(suite_uuid)
        if not suite:
            return lm_exceptions.report_problem(404, "Not Found",
                                                detail=messages.suite_not_found.format(suite_uuid))

        response = _get_workflow_or_problem(suite.workflow.uuid, suite.workflow.version)
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


@authorized
def suites_get_by_uuid(suite_uuid):
    response = _get_suite_or_problem(suite_uuid)
    return response if isinstance(response, Response) \
        else serializers.SuiteSchema().dump(response)


@authorized
def suites_get_status(suite_uuid):
    response = _get_suite_or_problem(suite_uuid)
    return response if isinstance(response, Response) \
        else serializers.SuiteStatusSchema().dump(response.status)


@authorized
def suites_get_instances(suite_uuid):
    response = _get_suite_or_problem(suite_uuid)
    return response if isinstance(response, Response) \
        else serializers.ListOfTestInstancesSchema().dump(response)


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


def suites_post_instance(suite_uuid):
    try:
        suite = lm.get_suite(suite_uuid)
        if not suite:
            return {"code": "404", "message": "Resource not found"}, 404
        if current_user and not current_user.is_anonymous:
            user_workflows = lm.get_user_workflows(current_user)
            if suite.workflow not in user_workflows:
                return f"The user cannot access suite {suite}", 401
        else:
            registry = g.workflow_registry if "workflow_registry" in g else None
            if registry is None:
                return "Unable to find a valid WorkflowRegistry", 404
            if suite.workflow not in registry.registered_workflows:
                return f"The registry cannot access suite {suite}", 401
    except lm_exceptions.EntityNotFoundException:
        return "Invalid ID", 400

    return "Not implemented", 501


def _get_instances_or_problem(instance_uuid):
    try:
        instance = lm.get_test_instance(instance_uuid)
        if not instance:
            return lm_exceptions.report_problem(404, "Not Found",
                                                detail=messages.suite_not_found.format(instance_uuid))
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
                                                extra_info={"reason": response.get_json()['detail']})
        return instance
    except lm_exceptions.EntityNotFoundException:
        return lm_exceptions.report_problem(404, "Not Found",
                                            detail=messages.instance_not_found.format(instance_uuid))


@authorized
def instances_get_by_id(instance_uuid):
    response = _get_instances_or_problem(instance_uuid)
    return response if isinstance(response, Response) \
        else serializers.TestInstanceSchema().dump(response)


@authorized
def instances_get_builds(instance_uuid, limit):
    response = _get_instances_or_problem(instance_uuid)
    logger.info("Number of builds to load: %r", limit)
    return response if isinstance(response, Response) \
        else serializers.ListOfTestBuildsSchema().dump(response.get_test_builds(limit=limit), many=True)


@authorized
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
    except ValueError as e:
        return lm_exceptions.report_problem(400, "Bad Request", detail=str(e))
    except Exception as e:
        logger.exception(e)
        return lm_exceptions.report_problem(500, "Internal Error", extra_info={"exception": str(e)})
