#!/usr/bin/env python3

import logging
import uuid

from lifemonitor import config, models
from lifemonitor.config import logger, db

WORK = {}

def workflows_get():
    results = models.Workflow.query.all()
    logger.debug("workflows_get. Got %s workflows", len(results))
    return results


def workflows_post(body):
    w = models.Workflow(
        workflow_id=uuid.uuid4(),
        name=body['name'])
    logger.debug("workflows_post. Created workflow with name '%s'", w.name)
    db.session.add(w)
    db.session.commit()
    logger.debug("Added and committed to DB")

    return str(w.workflow_id), 201


def workflows_get_by_id(wf_id):
    if wf_id in WORK:
        return WORK[wf_id]
    return 404


def workflows_delete(wf_id):
    if wf_id in WORK:
        del WORK[wf_id]
    return 204


def main():
    logger.info("Starting application")
    logger.debug(
        "REMOVE THIS LOG CALL - it includes the password! DB URI: %s",
        config.flask_app.config['SQLALCHEMY_DATABASE_URI'])
    db.create_all()
    config.connex_app.add_api('api.yaml', validate_responses=True)
    config.connex_app.run(port=8080)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
