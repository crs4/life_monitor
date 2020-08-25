#!/usr/bin/env python3
import logging
import connexion
from flask import request
from lifemonitor.api.services import LifeMonitor
from lifemonitor.common import EntityNotFoundException

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
    workflows = lm.get_registered_workflows()
    logger.debug("workflows_get. Got %s workflows", len(workflows))
    return [w.to_dict(test_suite=False, test_output=False) for w in workflows]


def workflows_post(body):
    w = lm.register_workflow(
        workflow_uuid=body['uuid'],
        workflow_version=body['version'],
        roc_link=body['roc_link'],
        name=body['name']
    )
    logger.debug("workflows_post. Created workflow with name '%s'", w.name)
    return {'wf_uuid': str(w.uuid), 'version': w.version}, 201


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
    test_suite = request.args.get('test_suite', False, type=bool)
    test_build = request.args.get('test_build', False, type=bool)
    test_output = request.args.get('test_output', False, type=bool)
    logger.debug("test_suites => %r %r", test_suite, type(test_suite))
    logger.debug("test_build => %r %r", test_build, type(test_build))
    logger.debug("test_output => %r %r", test_output, type(test_output))
    try:
        wf = lm.get_registered_workflow(wf_uuid, wf_version)
    except EntityNotFoundException:
        return "Invalid ID", 400

    if wf is not None:
        # Once we customize the JSON encoder or implement a smarter serialization
        # with Marshmellow we could simply return the value
        return wf.to_dict(test_suite=test_suite, test_build=test_build, test_output=test_output)

    return connexion.NoContent, 404


def workflows_delete(wf_uuid, wf_version):
    try:
        lm.deregister_workflow(wf_uuid, wf_version)
    except EntityNotFoundException:
        return "Invalid ID", 400

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
