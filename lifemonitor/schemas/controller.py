
import json
import logging

import yaml
from flask import jsonify, request

from lifemonitor.cache import Timeout, cached
from lifemonitor.exceptions import BadRequestException
from lifemonitor.schemas.validators import ConfigFileValidator

# Config a module level logger
logger = logging.getLogger(__name__)


@cached(timeout=Timeout.REQUEST)
def lifemonitor_json():
    with open('lifemonitor/schemas/lifemonitor.json') as f:
        return jsonify(json.load(f))


def validate():
    data = None
    logger.debug("Request: data", request.data)
    try:
        data = yaml.safe_load(request.data)
    except yaml.parser.ParserError:
        data = json.loads(request.data.decode())
    finally:
        if not data:
            raise BadRequestException(title="Invalid file format", detail="It should be a JSON or YAML file")
    logger.debug("JSON data to validate: %r", data)
    return ConfigFileValidator.validate(data).to_dict()
