# Copyright (c) 2020-2022 CRS4
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
import os
from typing import Dict

import pytest
import yaml

from lifemonitor.schemas.validators import ConfigFileValidator, ValidationError, ValidationResult

__current_path__ = os.path.dirname(os.path.realpath(__file__))


logger = logging.getLogger(__name__)


@pytest.fixture
def data() -> Dict:
    with open(f'{__current_path__}/test_data.yaml', 'r') as f:
        return yaml.unsafe_load(f)


@pytest.fixture
def schema() -> Dict:
    with open(f'{__current_path__}/../../../lifemonitor/schemas/lifemonitor.json', 'r') as f:
        return json.load(f)


def test_schema_loader(schema):
    assert sorted(ConfigFileValidator.schema.items()) == sorted(schema.items()), "Invalid schema"


def test_ref_solve(schema):

    ref = schema['definitions']['push_ref']
    logger.debug(ref)
    push_ref = ConfigFileValidator.find_definition(schema, "#/definitions/push_ref")
    assert push_ref == ref, "Invalid ref object"
    assert push_ref['properties']['update_registries']['default'] == [], "Invalid default value"


def test_valid_schema(data, schema):
    result: ValidationResult = ConfigFileValidator.validate(data)
    assert result is not None, "Result should be empty"
    assert isinstance(result, ValidationResult), "Unexpected validation response: 'valid' property not found"
    assert type(result.valid == bool), "'valid' property should be a boolean value"
    assert result.valid is True, "Unexpected validation response"


def test_default_for_public_property(data, schema):
    # remove public property from data
    del data['public']
    assert 'public' not in data, "public property should not be set on data"
    result: ValidationResult = ConfigFileValidator.validate(data)
    assert isinstance(result, ValidationResult), "Unexpected validation response: 'valid' property not found"
    assert result.input_data == data, "Unexpected input data"
    assert 'public' not in result.input_data, "Public property should not be set on data"
    print("Output data: %r" % result.output_data)
    assert result.output_data['public'] == schema['properties']['public']['default'], "Public property should be initialized with the defaul value"


def test_default_update_registries_of_branch(data, schema):

    del data['push']['branches'][0]['update_registries']
    assert 'update_registries' not in data['push']['branches'][0], "update_registries of branch main should not be set"
    result: ValidationError = ConfigFileValidator.validate(data)
    assert result is not None, "Result should be empty"
    assert result.valid is True, "Data should be valid"
    print(json.dumps(result.output_data, indent=2))
    assert 'update_registries' in result.output_data['push']['branches'][0],\
        "update_registries should be automatically initialized"
    assert result.output_data['push']['branches'][0]['update_registries'] == [], \
        "update_registries should be automatically initialized with default values"


def test_missing_branch_name(data):
    del data['push']['branches'][0]['name']
    result: ValidationError = ConfigFileValidator.validate(data)
    assert result is not None, "Result should be empty"
    assert isinstance(result, ValidationError), "Unexpected validation response: 'valid' property not found"
    assert type(result.valid == bool), "'valid' property should be a boolean value"
    assert result.valid is False, "Validation should fail"
    assert result.message == "'name' is a required property"
