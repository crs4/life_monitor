#!/usr/bin/env python3
import logging
import connexion
from flask import g
from flask_login import current_user
from lifemonitor.api.services import LifeMonitor
from lifemonitor.api.models import WorkflowRegistry
from lifemonitor.api import serializers
from lifemonitor.common import EntityNotFoundException, NotAuthorizedException, NotValidROCrateException
from lifemonitor.auth.oauth2.client.models import OAuthIdentity, OAuthIdentityNotFoundException
# Initialize a reference to the LifeMonitor instance
lm = LifeMonitor.get_instance()

# Config a module level logger
logger = logging.getLogger(__name__)


def _row_to_dict(row):
    d = {}
    for column in row.__table__.columns:
        d[column.name] = getattr(row, column.name)
    return d


def workflows_get():
    registry = g.workflow_registry if "workflow_registry" in g else None
    workflows = []
    if registry:
        workflows.extend(lm.get_registry_workflows(registry))
    elif not current_user.is_anonymous:
        workflows.extend(lm.get_user_workflows(current_user))

    logger.debug("workflows_get. Got %s workflows", len(workflows))
    return serializers.WorkflowSchema().dump(workflows, many=True)


def workflows_post(body):
    registry = g.workflow_registry if "workflow_registry" in g else None
    if not registry:
        try:
            registry = WorkflowRegistry.find_by_uri(body.get('registry_uri', None))
        except EntityNotFoundException as e:
            logger.debug(e)
    if registry is None:
        return "Unable to find a valid WorkflowRegistry", 404

    submitter = None
    logger.debug("Current user: %r --> anonymous: %r", current_user, current_user.is_anonymous)
    if current_user and not current_user.is_anonymous:
        submitter = current_user
    else:
        try:
            submitter_id = body.get('submitter_id', None)
            if submitter_id:
                identity = OAuthIdentity.find_by_provider(registry.name, submitter_id)
                submitter = identity.user
        except NameError as e:
            return f"Invalid request: {e.description}", 400
        except OAuthIdentityNotFoundException as e:
            logger.debug(e)
    if submitter is None:
        return "No valid submitter found", 404
    try:
        w = lm.register_workflow(
            workflow_registry=registry,
            workflow_submitter=submitter,
            workflow_uuid=body['uuid'],
            workflow_version=body['version'],
            roc_link=body['roc_link'],
            external_id=body.get("external_id", None),
            name=body.get('name', None)
        )
        logger.debug("workflows_post. Created workflow with name '%s'", w.name)
        return {'wf_uuid': str(w.uuid), 'version': w.version}, 201
    except NameError as e:
        return f"Invalid request: {e.description}", 400
    except OAuthIdentityNotFoundException:
        return f"Unable to find OAuth2 credentials for user {body.get('user_id', None)}", 401
    except NotValidROCrateException as e:
        return f"{e.description}", 400
    except NotAuthorizedException as e:
        return f"{e.description}", 401
    except Exception as e:
        logger.exception(e)
        return f"Internal Error: {e}", 500


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
    return connexion.NoContent, 501


def workflows_get_by_id(wf_uuid, wf_version):
    try:
        if current_user and not current_user.is_anonymous:
            wf = lm.get_user_workflow(wf_uuid, wf_version, current_user)
        else:
            wf = lm.get_registry_workflow(wf_uuid, wf_version)
    except EntityNotFoundException:
        return "Invalid ID", 400

    if wf is not None:
        return serializers.WorkflowSchema().dump(wf)

    return connexion.NoContent, 404




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


def suites_post(wf_uuid, wf_version, body):
    suite = lm.register_test_suite(
        workflow_uuid=wf_uuid,
        workflow_version=wf_version,
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
