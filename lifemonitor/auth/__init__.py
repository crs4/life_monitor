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
import lifemonitor.auth.oauth2 as oauth2
from .services import login_manager
from .controllers import blueprint as auth_blueprint
from .services import (
    current_user, current_registry, authorized,
    login_user, logout_user,
    login_registry, logout_registry,
    NotAuthorizedException
)

# Config a module level logger
logger = logging.getLogger(__name__)


def register_api(app, specs_dir):
    logger.debug("Registering auth blueprint")
    oauth2.client.register_api(app, specs_dir, "auth.merge")
    oauth2.server.register_api(app, specs_dir)
    app.register_blueprint(auth_blueprint)
    login_manager.init_app(app)


__all__ = [
    register_api, current_user, current_registry, authorized,
    login_user, logout_user, login_registry, logout_registry,
    NotAuthorizedException
]
