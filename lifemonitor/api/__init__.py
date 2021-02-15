import re
import pathlib
import logging
import connexion
from lifemonitor.api import models
from .serializers import ma

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
    models.registries.load_registry_types()
    ma.init_app(app)
    register_testing_services_credentials(app.config)
