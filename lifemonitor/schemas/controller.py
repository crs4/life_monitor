
import json
import logging

import yaml
from flask import jsonify, request

from lifemonitor.cache import Timeout, cached
from lifemonitor.schemas.validators import ConfigFileValidator, Validator

# Config a module level logger
logger = logging.getLogger(__name__)


@cached(timeout=Timeout.REQUEST)
def lifemonitor_json():
    with open('lifemonitor/schemas/lifemonitor.json') as f:
        return jsonify(json.load(f))

