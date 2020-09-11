import os
import logging
from lifemonitor.api.models import WorkflowRegistry
from lifemonitor.api.services import LifeMonitor

THIS_DIR = os.path.dirname(os.path.abspath(__file__))

logger = logging.getLogger()


def test_workflow_registration(app_context, clean_db, session_transaction, user, workflow):
    r = WorkflowRegistry.get_instance()
    logger.debug(r._client.api_base_url)
    logger.debug("Workflows: %r", r.get_workflows())
    lm = LifeMonitor.get_instance()
    lm.register_workflow(workflow['uuid'], workflow['version'],
                         workflow['roc_link'], workflow['name'])
