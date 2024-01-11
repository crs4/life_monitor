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

import logging

import requests
from flask import request, session

logger = logging.getLogger(__name__)


class RequestHelper:

    _DEFAULT_KEY_ = "__lm.auth.request__"

    @classmethod
    def push_request(cls, key=None, url=None, params=None, headers=None):
        _params = request.args.to_dict()
        _headers = {
            'Authorization': request.headers.get('Authorization', ''),
            'Cookies': request.headers.get('Cookies', '')
        }
        if params:
            _params.update(params)
        session[key or cls._DEFAULT_KEY_] = {
            'url': url if url else request.url,
            'method': request.method,
            'params': _params,
            'data': request.data,
            'headers': headers if headers else _headers
        }
        logger.debug("Request save on session: %r", request)

    @classmethod
    def pop_request(cls, key=None):
        return session.pop(key or cls._DEFAULT_KEY_, False)

    @classmethod
    def response(cls, key=None):
        request = cls.pop_request(key)
        logger.debug("Pop the request from session: %r", request)
        if request:
            method = getattr(requests, request['method'].lower())
            logger.debug("The method: %r", method)
            res = method(request['url'],
                         params=request['params'],
                         headers=request['headers'],
                         data=request['data'])
            return (res.text, res.status_code, res.headers.items())
        return None
