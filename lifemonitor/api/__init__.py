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

import re
import pathlib
import logging
import connexion
from .serializers import ma
from lifemonitor.api import models
from lifemonitor.api import registries

logger = logging.getLogger(__name__)


def register_testing_services_credentials(conf):
    token_mgt = models.TestingServiceTokenManager.get_instance()
    pattern = re.compile(r'(.+)_TESTING_SERVICE_URL')
    for k in conf:
        service_match = pattern.match(k)
        if service_match:
            try:
                url = conf[k]
                token = conf[f"{service_match.group(1)}_TESTING_SERVICE_TOKEN"]
                token_mgt.add_token(url, models.TestingServiceToken('token', token))
            except KeyError as e:
                logger.debug(e)


def register_api(app, specs_dir):
    api = connexion.Api(pathlib.Path(specs_dir, 'api.yaml'),
                        validate_responses=True,
                        arguments={'global': 'global_value'})
    app.register_blueprint(api.blueprint)
    registries.load_registry_types()
    ma.init_app(app)
    register_testing_services_credentials(app.config)
