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

import logging
import sys
from typing import Dict

from flask import Blueprint, render_template, request, url_for


# Config a module level logger
logger = logging.getLogger(__name__)

blueprint = Blueprint(
    "errors",
    __name__,
    url_prefix="/error",
    template_folder="templates",
    static_folder="static",
    static_url_path="../static",
)

# reference to this module
error_handlers = sys.modules[__name__]


@blueprint.route("/")
def parametric_page():
    code = request.args.get("code", 500, type=str)
    try:
        handler = getattr(error_handlers, f"handle_{code}")
        logger.debug(f"Handling error code: {code}")
        return handler()
    except ValueError as e:
        logger.error(f"Invalid error code: {code}")
        return handle_500()


@blueprint.route("/400")
def handle_400(e: Exception = None):

@blueprint.route("/404")
def handle_404(e: Exception = None):
    return handle_error(
        {
            "title": "LifeMonitor: Page not found",
            "code": "404",
            "description": "Page not found",
        }
    )


@blueprint.route("/429")
def handle_429(e: Exception = None):
    return handle_error(
        {
            "title": "LifeMonitor: API rate limit exceeded",
            "code": "429",
            "description": "API rate limit exceeded",
        }
    )


@blueprint.route("/500")
def handle_500(e: Exception = None):
    return handle_error(
        {
            "title": "LifeMonitor: Internal Server Error",
            "code": "500",
            "description": "Internal Server Error: the server encountered a temporary error and could not complete your request",
        }
    )


@blueprint.route("/502")
def handle_502(e: Exception = None):
    return handle_error(
        {
            "title": "LifeMonitor: Bad Gateway",
            "code": "502",
            "description": "Internal Server Error: the server encountered a temporary error and could not complete your request",
        }
    )


def handle_error(error: Dict[str, str]):
    back_url = request.args.get("back_url", url_for("auth.profile"))
    # parse Accept header
    accept = request.headers.get("Accept", "text/html")
    if "application/json" in accept:
        # return error as JSON
        return error, error.get("code", 500)
    try:
        return (
            render_template("errors/parametric.j2", **error, back_url=back_url),
            error["code"],
        )
    except Exception as e:
        logger.error(f"Error rendering error page: {e}")
        return "Internal Server Error", 500


def register_api(app):
    logger.debug("Registering errors blueprint")
    app.register_blueprint(blueprint)
