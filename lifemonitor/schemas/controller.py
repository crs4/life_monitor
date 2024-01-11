# Copyright (c) 2020-2024 CRS4
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

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
