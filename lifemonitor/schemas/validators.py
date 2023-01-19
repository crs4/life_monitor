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

import requests
from jsonschema import ValidationError as VE
from jsonschema import validate


class Result:

    valid: bool

    def __init__(self, valid: bool = True) -> None:
        self.valid = valid

    def to_dict(self) -> Dict:
        return {'valid': self.valid}


class ValidationError(Result):

    message: str
    error: str
    exception: VE

    def __init__(self, ex: VE) -> None:
        super().__init__(False)
        self.message = ex.message
        self.error = str(ex)
        self.exception = ex

    def to_dict(self) -> Dict:
        return {'valid': False, 'message': self.message, 'error': self.error}


class Validator:

    __schema__ = None

    @classmethod
    def __get_schema__(cls) -> Dict:
        if not cls.__schema__:
            cls.__schema__ = cls.load_schema()
        return cls.__schema__

    @classmethod
    def load_schema(cls) -> Dict:
        raise NotImplemented('load_schema not implemented')

    @classmethod
    def validate(cls, data: Dict, schema: Dict = None) -> Result:
        try:
            validate(instance=data, schema=schema or cls.__get_schema__())
            return Result(valid=True)
        except VE as e:
            return ValidationError(e)


class ConfigFileValidator(Validator):

    SCHEMA_PATH: str = "./lifemonitor/schemas/lifemonitor.json"

    @classmethod
    def load_schema(cls) -> Dict:
        with open(cls.SCHEMA_PATH, 'r') as f:
            return json.load(f)
