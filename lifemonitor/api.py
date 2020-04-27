#!/usr/bin/env python3

import connexion
import logging
import os
import uuid


WORK = {}

def workflows_get():
    return [ v for v in WORK.values() ]


def workflows_post(body):
    w = { 'id': str(uuid.uuid4()), 'name': body['name'] }
    WORK[w['id']] = w
    return w['id'], 201


def workflows_get_by_id(wf_id):
    if wf_id in WORK:
        return WORK[wf_id]
    return 404


def workflows_delete(wf_id):
    if wf_id in WORK:
        del WORK[wf_id]
    return 204


def main():
    my_dir = os.path.abspath(os.path.dirname(__file__))
    app = connexion.App('LM', specification_dir=my_dir)
    app.add_api('api.yaml', validate_responses=True)
    app.run(port=8080)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
