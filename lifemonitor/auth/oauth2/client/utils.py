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
        try:
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
        except Exception as e:
            logger.debug(e)
            return False
