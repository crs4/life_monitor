
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
    '''
    Validates the data in the request body against the lifemonitor.json schema
    :return: a JSON representation of the validation result

    :raises BadRequestException: if the data in the request body is not valid
    :raises ValidationError: if the data in the request body is not valid
    '''
    logger.debug("Request data: %r", request.data)
    # Try to parse the data as YAML
    try:
        data = yaml.safe_load(request.data)
        if data is None:
            raise ValueError("Data is None after YAML parsing")
    except (yaml.parser.ParserError, ValueError):
        try:
            data = json.loads(request.data.decode())
        except json.JSONDecodeError:
            raise BadRequestException(title="Invalid file format", detail="It should be a JSON or YAML file")
    # Check if the data is empty
    if not data:
        raise BadRequestException(title="Invalid file format", detail="It should be a JSON or YAML file")
    logger.debug("JSON data to validate: %r", data)
    # Validate the data
    return ConfigFileValidator.validate(data).to_dict()
