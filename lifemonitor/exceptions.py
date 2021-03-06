# Copyright (c) 2020-2021 CRS4
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

import logging

from flask import Response, current_app, request
from lifemonitor import serializers
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


class LifeMonitorException(Exception):

    def __init__(self, title=None, detail=None,
                 type="about:blank", status=500, instance=None, **kwargs):
        self.title = title
        self.detail = detail
        self.type = type
        self.status = status
        self.instance = instance
        if len(kwargs) > 0:
            self.extra_info = kwargs
        if instance is None:
            try:
                self.instance = request.url
            except Exception:
                pass

    def __repr__(self):
        return f"[{self.status}] {self.title}: {self.detail}"

    def to_json(self):
        return serializers.ProblemDetailsSchema().dumps(self)


class NotImplementedException(LifeMonitorException):

    def __init__(self, title="Not Implemented", detail=None,
                 type="about:blank", status=501, instance=None, **kwargs):
        super().__init__(title, detail, type, status, instance, **kwargs)


class UnsupportedOperationException(LifeMonitorException):

    def __init__(self, detail="The operation has not been implemented yet",
                 type="about:blank", status=501, instance=None, **kwargs):
        super().__init__(title="Not Implemented",
                         detail=detail, status=status, **kwargs)


class NotAuthorizedException(LifeMonitorException):
    def __init__(self, detail=None,
                 type="about:blank", status=401, instance=None, **kwargs):
        super().__init__(title="Unauthorized",
                         detail=detail, status=status, **kwargs)


class Forbidden(LifeMonitorException):
    def __init__(self, detail=None,
                 type="about:blank", status=403, instance=None, **kwargs):
        super().__init__(title="Forbidden",
                         detail=detail, status=status, **kwargs)


class SpecificationNotDefinedException(LifeMonitorException):

    def __init__(self, detail="Specification not defined",
                 type="about:blank", status=400, instance=None, **kwargs):
        super().__init__(title="Bad request",
                         detail=detail, status=status, **kwargs)


class SpecificationNotValidException(LifeMonitorException):

    def __init__(self, detail="Invalid specification",
                 type="about:blank", status=400, instance=None, **kwargs):
        super().__init__(title="Bad request",
                         detail=detail, status=status, **kwargs)


class EntityNotFoundException(LifeMonitorException):

    def __init__(self, entity_class, detail=None, entity_id=None, **kwargs) -> None:
        if not detail:
            detail = f"{entity_class.__name__} '{entity_id}' not found" \
                if entity_id else f"{entity_class.__name__} not found"
        kwargs["resource_type"] = entity_class.__name__
        if entity_id:
            kwargs["resource_identifier"] = entity_id
        super().__init__(
            title="Resource not found",
            detail=detail, status=404, **kwargs)
        self.entity_class = entity_class
        self.entity_id = entity_id

    def __str__(self):
        return self.detail


class WorkflowVersionConflictException(LifeMonitorException):

    def __init__(self, workflow_uuid, workflow_version, detail=None, **kwargs) -> None:
        if not detail:
            detail = f"Version v{workflow_version} of the workflow {workflow_uuid} already registered"
        super().__init__(
            title="Workflow version conflict",
            detail=detail, status=409, **kwargs)


class NotValidROCrateException(LifeMonitorException):

    def __init__(self, detail="Not valid RO Crate",
                 type="about:blank", status=501, instance=None, **kwargs):
        super().__init__(title="Bad request",
                         detail=detail, status=status, **kwargs)


class WorkflowRegistryNotSupportedException(LifeMonitorException):

    def __init__(self, detail="Workflow Registry not supported",
                 type="about:blank", status=400, instance=None, **kwargs):
        super().__init__(title="Bad request",
                         detail=detail, status=status, **kwargs)


class TestingServiceNotSupportedException(LifeMonitorException):

    def __init__(self, detail="Testing service not supported",
                 type="about:blank", status=400, instance=None, **kwargs):
        super().__init__(title="Bad request",
                         detail=detail, status=status, **kwargs)


class TestingServiceException(LifeMonitorException):

    def __init__(self, detail="",
                 type="about:blank", status=500, instance=None, **kwargs):
        super().__init__(title="Testing service error",
                         detail=detail, status=status, **kwargs)


def handle_exception(e: Exception):
    """Return JSON instead of HTML for HTTP errors."""
    # start with the correct headers and status code from the error
    if current_app and current_app.config['DEBUG']:
        logger.exception(e)
    if isinstance(e, LifeMonitorException):
        return Response(response=e.to_json(),
                        status=e.status,
                        mimetype="application/problem+json")
    if isinstance(e, HTTPException):
        return report_problem(status=e.code,
                              title=e.__class__.__name__,
                              detail=getattr(e, "description", None))
    else:
        return report_problem(status=500,
                              title="Internal Server Error",
                              detail=getattr(e, "description", None),
                              extra_info={
                                  "exception_type": e.__class__.__name__,
                                  "exception_value": str(e)
                              })


def report_problem(status, title, detail=None, type=None, instance=None, extra_info=None):
    """
    Returns a `Problem Details <https://tools.ietf.org/html/draft-ietf-appsawg-http-problem-00>`_ error response.
    """
    if not type:
        type = 'about:blank'

    problem_response = {'type': type, 'title': title, 'status': status}
    if detail:
        problem_response['detail'] = detail
    if instance:
        problem_response['instance'] = instance
    else:
        try:
            problem_response['instance'] = request.url
        except Exception:
            pass
    if extra_info:
        problem_response['extra_info'] = extra_info

    return Response(response=serializers.ProblemDetailsSchema().dumps(problem_response),
                    status=status, mimetype="application/problem+json")


def report_problem_from_exception(e: Exception):
    return handle_exception(e)
