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
from typing import Dict

from jsonschema import ValidationError as VE
from jsonschema import validate, Draft7Validator


import logging

logger = logging.getLogger(__name__)

__DEFINITIONS_PREFIX__ = '#/definitions/'


class ValidationResult:

    valid: bool
    input_data: object
    output_data: object

    def __init__(self, valid: bool,
                 input_data: object, output_data: object = None) -> None:
        self.valid = valid
        self.input_data = input_data
        self.output_data = output_data

    def to_dict(self) -> Dict:
        return {'valid': self.valid, 'data': self.output_data}


class ValidationError(ValidationResult):

    message: str
    error: str
    exception: VE

    def __init__(self, ex: VE, input_data: object) -> None:
        super().__init__(valid=False, input_data=input_data)
        self.message = ex.message
        self.error = str(ex)
        self.exception = ex

    def to_dict(self) -> Dict:
        return {'valid': False, 'message': self.message, 'error': self.error}


class Validator:

    __schema__ = None

    __validator_class__ = Draft7Validator

    @classmethod
    def __get_schema__(cls) -> Dict:
        if not cls.__schema__:
            cls.__schema__ = cls.load_schema()
        return cls.__schema__

    @classmethod
    @property
    def schema(cls) -> Dict:
        return cls.__get_schema__()

    @classmethod
    def load_schema(cls) -> Dict:
        raise NotImplementedError('load_schema not implemented')

    @classmethod
    def validate(cls, data: Dict, schema: Dict = None) -> ValidationResult:
        try:
            # set the schema
            schema = schema or schema or cls.__get_schema__()

            # Validate the data against the schema
            validate(instance=data, schema=schema)

            # set defaults
            output = cls.set_defaults(data=data, schema=schema, subschema=schema)

            logger.debug("Validated data: %r", json.dumps(output, indent=2))
            return ValidationResult(valid=True, input_data=data,
                                    output_data=output)
        except VE as e:
            return ValidationError(e, input_data=data)

    @staticmethod
    def find_definition(schema: Dict, ref: str):
        definitionName = ref.removeprefix(__DEFINITIONS_PREFIX__)
        return schema['definitions'][definitionName]

    @classmethod
    def set_defaults(cls, data: Dict, schema: Dict, subschema: Dict = None) -> ValidationResult:
        result = data
        logger.debug("Processing %r" % (data))
        logger.debug("Subschema %r" % (subschema))

        if subschema['type'] not in ('object', 'array'):
            logger.debug("Simple data type")
            if not data:
                if 'default' in subschema:
                    return subschema['default']
                elif '$ref' in subschema:
                    definition = cls.find_definition(subschema['$ref'])
                    if definition:
                        return cls.set_defaults(data, schema, definition)
            return result

        elif subschema['type'] == 'array':
            logger.debug("Array data type")
            result = []
            definition = None
            if '$ref' in subschema['items']:
                definition = cls.find_definition(schema, subschema['items']['$ref'])
            else:
                definition = subschema['items']
            if "default" in subschema:
                result = subschema['default']
            elif data:
                for item in data:
                    result.append(cls.set_defaults(item, schema, definition))
            return result

        else:  # type == 'object'
            result = {}
            logger.debug("Object type")
            for field, subschema in subschema["properties"].items():
                logger.debug("Processing field: %r", field)
                field_value = cls.set_defaults(data[field] if data and field in data else None, schema, subschema)
                if field_value is not None:
                    result[field] = field_value

            return result


class ConfigFileValidator(Validator):

    SCHEMA_PATH: str = "./lifemonitor/schemas/lifemonitor.json"

    @classmethod
    def load_schema(cls) -> Dict:
        with open(cls.SCHEMA_PATH, 'r') as f:
            return json.load(f)
