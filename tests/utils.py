import logging
import lifemonitor.db as lm_db
from lifemonitor.api import models
from lifemonitor.api.services import LifeMonitor

logger = logging.getLogger(__name__)

_USERS_ENDPOINT = '/users'
_REGISTRIES_ENDPOINT = '/registries'
_WORKFLOWS_ENDPOINT = '/workflows'
_SUITES_ENDPOINT = '/suites'
_INSTANCES_ENDPOINT = '/instances'


def build_users_path(user_id=None):
    if user_id:
        return f"{_USERS_ENDPOINT}/{user_id}"
    return _USERS_ENDPOINT


def build_registries_path(registry_uuid=None):
    if registry_uuid:
        return f"{_REGISTRIES_ENDPOINT}/{registry_uuid}"
    return _REGISTRIES_ENDPOINT


def build_workflow_path(workflow=None):
    if workflow:
        return f"{_WORKFLOWS_ENDPOINT}/{workflow['uuid']}/{workflow['version']}"
    return _WORKFLOWS_ENDPOINT


def build_suites_path(suite_uuid=None):
    if suite_uuid:
        return f"{_SUITES_ENDPOINT}/{suite_uuid}"
    return _SUITES_ENDPOINT


def build_instances_path(instances_uuid=None):
    if instances_uuid:
        return f"{_INSTANCES_ENDPOINT}/{instances_uuid}"
    return _INSTANCES_ENDPOINT


def assert_properties_exist(properties, object):
    for p in properties:
        try:
            assert p in object, f"The property '{p}' is not set!"
        except TypeError:
            assert hasattr(object, p), f"The property '{p}' is not set!"


def assert_status_code(expected, actual, message=None):
    assert expected == actual, message or f"Expected status code {expected}, actual status code {actual}"


def assert_error_message(message, error):
    assert message in str(error), "Unexpected error message"


def pick_workflow(app_user, name=None):
    assert len(app_user["workflows"]) > 0, "No workflow found to register"
    # pick one user workflow and register it
    if name is None:
        return app_user["workflows"].pop()
    for w in app_user["workflows"]:
        if w["name"] == name:
            return w
    raise RuntimeError(f"Unable to find the workflow {name}")


def register_workflow(app_user, w):
    # get the registry
    r = models.WorkflowRegistry.find_by_uri(w["registry_uri"])
    # register
    lm = LifeMonitor.get_instance()
    workflow = lm.register_workflow(app_user["user"],
                                    w['uuid'], w['version'], w['roc_link'], r, name=w['name'])
    return w, workflow


def register_workflows(app_user):
    for w in app_user["workflows"]:
        try:
            logger.debug("Registering workflow: %r", w)
            register_workflow(app_user, w)
        except Exception as e:
            logger.debug(e)
            lm_db.db.session.rollback()


def pick_and_register_workflow(app_user, name=None):
    # pick one user workflow and register it
    return register_workflow(app_user, pick_workflow(app_user, name))


def not_shared_workflows(user1, user2, skip=None):
    return [w for w in user1['workflows']
            if skip and w['name'] not in skip
            if w['uuid'] not in [_['uuid'] for _ in user2['workflows']]]
