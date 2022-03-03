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

from __future__ import annotations

import logging

from flask import Blueprint, Flask, request
from lifemonitor.integrations.github.events import get_event_map
from lifemonitor.integrations.github.models import GithubEvent, LifeMonitorGithubApp

# Config a module level logger
logger = logging.getLogger(__name__)

# Register Handlers
__event_handlers__ = get_event_map()

# Integration Blueprint
blueprint = Blueprint("github_integration", __name__,
                      template_folder='templates',
                      static_folder="static", static_url_path='/static')


@blueprint.route("/integrations/github", methods=("POST",))
def handle_event():
    logger.debug("Request header keys: %r", [k for k in request.headers.keys()])
    logger.debug("Request header values: %r", request.headers)
    if not LifeMonitorGithubApp.check_initialization():
        return "GitHub Integration not configured", 503
    valid = LifeMonitorGithubApp.validate_signature(request)
    logger.debug("Signature valid?: %r", valid)
    if not valid:
        return "Signature Invalid", 401
    event = GithubEvent.from_request()
    event_handler = __event_handlers__.get(event['type'], None)
    logger.debug("Event: %r", event)
    if not event_handler:
        action = f"- action: {event['action']}" if event['action'] else None
        logger.warning(f"No event handler registered for the event GitHub event '{event['type']}' {action}")
        return f"No handler registered for the '{event['type']}' event", 204
    else:
        return event_handler(event)


def init_integration(app: Flask):
    # Initialize GitHub App Integration
    app_identifier = app.config.get('GITHUB_INTEGRATION_APP_ID')
    webhook_secret = app.config.get('GITHUB_INTEGRATION_WEB_SECRET')
    service_token = app.config.get('GITHUB_INTEGRATION_SERVICE_TOKEN')
    service_repository = app.config.get('GITHUB_INTEGRATION_SERVICE_REPOSITORY')
    private_key_path = app.config.get('GITHUB_INTEGRATION_PRIVATE_KEY_PATH')    
    LifeMonitorGithubApp.init(app_identifier, private_key_path, webhook_secret, service_token,
                              service_repository_full_name=service_repository)
    app.register_blueprint(blueprint)
    logger.info("Integration registered for GitHub App: %r", app_identifier)
