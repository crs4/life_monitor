#!/usr/bin/env python3

import os
import uuid

import connexion
import sqlalchemy

from lifemonitor import config, models
from lifemonitor.config import logger
from lifemonitor.models import db

WORK = {}

connex_app = None

def _row_to_dict(row):
    d = {}
    for column in row.__table__.columns:
        d[column.name] = getattr(row, column.name)
    return d


def workflows_get():
    results = models.Workflow.query.all()
    logger.debug("workflows_get. Got %s workflows", len(results))
    return [ _row_to_dict(row) for row in results ]


def workflows_post(body):
    w = models.Workflow(
        workflow_id=uuid.uuid4(),
        name=body['name'])
    logger.debug("workflows_post. Created workflow with name '%s'", w.name)
    db.session.add(w)
    db.session.commit()
    logger.debug("Added and committed to DB")

    return str(w.workflow_id), 201


def workflows_put(wf_id, body):
    logger.debug("PUT called for wf_id %s", wf_id)
    try:
        wf = models.Workflow.query.get(wf_id)
    except sqlalchemy.exc.DataError:
        return "Invalid ID", 400
    wf.name = body['name']
    db.session.commit()
    return connexion.NoContent, 200


def workflows_get_by_id(wf_id):
    try:
        wf = models.Workflow.query.get(wf_id)
    except sqlalchemy.exc.DataError:
        return "Invalid ID", 400

    if wf is not None:
        # Once we customize the JSON encoder or implement a smarter serialization
        # with Marshmellow we could simply return the value
        return _row_to_dict(wf)

    return connexion.NoContent, 404


def workflows_delete(wf_id):
    try:
        wf = models.Workflow.query.get(wf_id)
    except sqlalchemy.exc.DataError:
        return "Invalid ID", 400

    if wf is None:
        return connexion.NoContent, 200

    db.session.delete(wf)
    db.session.commit()
    logger.debug("Committed")
    return connexion.NoContent, 204


def create_app():
    base_dir = os.path.abspath(os.path.dirname(__file__))
    global connex_app
    connex_app = connexion.App('LM', specification_dir=base_dir)
    flask_app = connex_app.app

    with flask_app.app_context():
        config.configure_logging(flask_app)
        logger.info("Starting application")

        models.config_db_access(flask_app)

    connex_app.add_api('api.yaml', validate_responses=True)
    connex_app.run(port=8080)


if __name__ == '__main__':
    create_app()
