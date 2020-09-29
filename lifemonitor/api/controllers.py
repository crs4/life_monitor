#!/usr/bin/env python3
import logging
import connexion
from flask import g
from lifemonitor.lang import messages
from lifemonitor.auth import current_user, current_registry, authorized
from lifemonitor.api.services import LifeMonitor
from lifemonitor.api.models import TestInstance
from lifemonitor.api import serializers
import werkzeug.exceptions as http_exceptions
from lifemonitor.common import EntityNotFoundException, NotAuthorizedException, NotValidROCrateException, LifeMonitorException
from lifemonitor.auth.oauth2.client.models import OAuthIdentityNotFoundException
from lifemonitor.common import report_problem
# Initialize a reference to the LifeMonitor instance
lm = LifeMonitor.get_instance()

# Config a module level logger
logger = logging.getLogger(__name__)


def _row_to_dict(row):
    d = {}
    for column in row.__table__.columns:
        d[column.name] = getattr(row, column.name)
    return d


@authorized
def workflows_get():
    workflows = []
    if current_registry:
        workflows.extend(lm.get_registry_workflows(current_registry))
    elif not current_user.is_anonymous:
        workflows.extend(lm.get_user_workflows(current_user))
    else:
        return report_problem(401, "Unauthorized", detail=messages.no_user_in_session)
    logger.debug("workflows_get. Got %s workflows", len(workflows))
    return serializers.WorkflowSchema().dump(workflows, many=True)


@authorized
def workflows_post(body):
    registry = current_registry
    if registry and 'registry_uri' in body:
        return report_problem(400, "Bad request",
                              detail=messages.unexpected_registry_uri)
    if not registry:
        if 'registry_uri' not in body:
            return report_problem(400, "Bad request",
                                  detail=messages.no_registry_uri_provided)
        registry_uri = body.get('registry_uri', None)
        try:
            registry = lm.get_workflow_registry_by_uri(registry_uri)
        except EntityNotFoundException:
            return report_problem(404, "Not Found",
                                  detail=messages.no_registry_found.format(registry_uri))
    submitter = None
    submitter_id = None
    if not current_user or current_user.is_anonymous:  # the client is a registry
        try:
            submitter_id = body['submitter_id']
        except KeyError:
            return report_problem(400, "Bad request",
                                  detail=messages.no_submitter_id_provided)
    try:
        # Try to find the identity of the submitter
        identity = lm.find_registry_user_identity(registry,
                                                  internal_id=current_user.id,
                                                  external_id=submitter_id)
        submitter = identity.user
        w = lm.register_workflow(
            workflow_registry=registry,
            workflow_submitter=submitter,
            workflow_uuid=body['uuid'],
            workflow_version=body['version'],
            roc_link=body['roc_link'],
            external_id=body.get("external_id", None),
            name=body.get('name', None)
        )
        logger.debug("workflows_post. Created workflow '%s' (ver.%s)", w.uuid, w.version)
        return {'wf_uuid': str(w.uuid), 'wf_version': w.version}, 201
    except KeyError as e:
        return report_problem(400, "Bad Request", extra_info={"exception": str(e)},
                              detail=messages.input_data_missing)
    except OAuthIdentityNotFoundException:
        return report_problem(401, "Unauthorized",
                              detail=messages.no_user_oauth_identity_on_registry
                              .format(submitter_id or current_user.id, registry.name))
    except NotValidROCrateException as e:
        return report_problem(400, "Bad Request", extra_info={"exception": str(e)},
                              detail=messages.invalid_ro_crate)
    except NotAuthorizedException as e:
        return report_problem(403, "Forbidden", extra_info={"exception": str(e)},
                              detail=messages.not_authorized_registry_access
                              .format(registry.name))
    except Exception as e:
        logger.exception(e)
        raise LifeMonitorException(title="Internal Error", detail=str(e))


def workflows_put(wf_uuid, wf_version, body):
    # TODO: to be implemented
    logger.debug("PUT called for workflow (%s,%s)", wf_uuid, wf_version)
    # try:
    #     wf = model.Workflow.query.get(wf_id)
    # except sqlalchemy.exc.DataError:
    #     return "Invalid ID", 400
    # wf.name = body['name']
    # db.session.commit()
    # return connexion.NoContent, 200
    raise http_exceptions.NotImplemented()


def workflows_get_by_id(wf_uuid, wf_version):
    try:
        if current_user and not current_user.is_anonymous:
            wf = lm.get_user_workflow(wf_uuid, wf_version, current_user)
        else:
            registry = g.workflow_registry if "workflow_registry" in g else None
            if registry is None:
                return "Unable to find a valid WorkflowRegistry", 404
            wf = lm.get_registry_workflow(wf_uuid, wf_version, registry)
    except EntityNotFoundException:
        return "Invalid ID", 400

    if wf is not None:
        return serializers.WorkflowSchema().dump(wf)

    return connexion.NoContent, 404


def workflows_get_latest_by_id(wf_uuid):
    # try:
    #     if current_user and not current_user.is_anonymous:
    #         wf = lm.get_user_workflow(wf_uuid, wf_version, current_user)
    #     else:
    #         wf = lm.get_registry_workflow(wf_uuid, wf_version)
    # except EntityNotFoundException:
    #     return "Invalid ID", 400

    # if wf is not None:
    #     return serializers.WorkflowSchema().dump(wf)

    # return connexion.NoContent, 404
    return connexion.problem(title="Not implemented", status=501)


def workflows_get_status(wf_uuid, wf_version):
    try:
        logger.debug("Current user: %r", current_user)
        if current_user and not current_user.is_anonymous:
            wf = lm.get_user_workflow(wf_uuid, wf_version, current_user)
        else:
            registry = g.workflow_registry if "workflow_registry" in g else None
            if registry is None:
                return "Unable to find a valid WorkflowRegistry", 404
            wf = lm.get_registry_workflow(wf_uuid, wf_version, registry)
    except EntityNotFoundException:
        return "Invalid ID", 400

    if wf is not None:
        result = serializers.WorkflowStatusSchema().dump(wf.status)
        logger.debug(result)
        return result

    return connexion.NoContent, 404


def workflows_delete(wf_uuid, wf_version):
    try:
        if current_user and not current_user.is_anonymous:
            lm.deregister_workflow(wf_uuid, wf_version, current_user)
        elif "registry" in g:
            lm.deregister_workflow(wf_uuid, wf_version)
    except EntityNotFoundException as e:
        logger.exception(e)
        return "Invalid ID", 400
    except NotAuthorizedException as e:
        logger.exception(e)
        return "Invalid credentials", 401
    except Exception as e:
        logger.exception(e)
        return "Internal Error", 500

    return connexion.NoContent, 204


def workflows_get_suites(wf_uuid, wf_version):
    try:
        logger.debug("Current user: %r", current_user)
        if current_user and not current_user.is_anonymous:
            wf = lm.get_user_workflow(wf_uuid, wf_version, current_user)
        else:
            registry = g.workflow_registry if "workflow_registry" in g else None
            if registry is None:
                return "Unable to find a valid WorkflowRegistry", 404
            wf = lm.get_registry_workflow(wf_uuid, wf_version, registry)
    except EntityNotFoundException:
        return "Invalid ID", 400

    if wf is not None:
        result = serializers.SuiteSchema().dump(wf.test_suites, many=True)
        logger.debug(result)
        return result

    return connexion.NoContent, 404


def suites_get_by_uuid(suite_uuid):
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
    except EntityNotFoundException:
        return "Invalid ID", 400

    return serializers.SuiteSchema().dump(suite)


def suites_get_status(suite_uuid):
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
    except EntityNotFoundException:
        return "Invalid ID", 400

    return serializers.SuiteStatusSchema().dump(suite.status)


def suites_get_instances(suite_uuid):
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
    except EntityNotFoundException:
        return "Invalid ID", 400

    return serializers.ListOfTestInstancesSchema().dump(suite)


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
    except EntityNotFoundException:
        return "Invalid ID", 400

    return "Not implemented", 501


def suites_post(wf_uuid, wf_version, body):
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
        lm.deregister_test_suite(suite_uuid)
    except EntityNotFoundException:
        return "Invalid ID", 400

    return connexion.NoContent, 204


def _instances_get_by_id(instance_uuid):
    try:
        instance = lm.get_test_instance(instance_uuid)
        if not instance:
            return {"code": "404", "message": "Resource not found"}, 404
        if current_user and not current_user.is_anonymous:
            user_workflows = lm.get_user_workflows(current_user)
            if instance.test_suite.workflow not in user_workflows:
                return f"The user cannot access suite {instance}", 401
        else:
            registry = g.workflow_registry if "workflow_registry" in g else None
            if registry is None:
                return "Unable to find a valid WorkflowRegistry", 404
            if instance.test_suite.workflow not in registry.registered_workflows:
                return f"The registry cannot access suite {instance}", 401
    except EntityNotFoundException:
        return "Invalid ID", 400

    return instance


def instances_get_by_id(instance_uuid):
    instance = _instances_get_by_id(instance_uuid)
    if not isinstance(instance, TestInstance):
        return instance
    return serializers.TestInstanceSchema().dump(instance)


def instances_get_builds(instance_uuid, limit):
    instance = _instances_get_by_id(instance_uuid)
    if not isinstance(instance, TestInstance):
        return instance
    # TODO: implement pagination using 'limit' param
    return serializers.ListOfTestBuildsSchema().dump(instance)


def instances_builds_get_by_id(instance_uuid, build_id):
    instance = _instances_get_by_id(instance_uuid)
    if not isinstance(instance, TestInstance):
        return instance
    # TODO: implement pagination using 'limit_bytes' param
    for build in instance.test_builds:
        if build.id == build_id:
            return serializers.BuildSummarySchema().dump(build)
    return "Test Build not found", 404


def instances_builds_get_logs(instance_uuid, build_id, offset_bytes, limit_bytes):
    instance = _instances_get_by_id(instance_uuid)
    if not isinstance(instance, TestInstance):
        return instance
    # TODO: implement pagination using 'limit_bytes' param
    for build in instance.test_builds:
        if build.id == build_id:
            return build.output
    return "Test Build not found", 404
