import pathlib
import connexion
from .serializers import ma
from lifemonitor.api import registries


def register_api(app, specs_dir):
    api = connexion.Api(pathlib.Path(specs_dir, 'api.yaml'),
                        validate_responses=True,
                        arguments={'global': 'global_value'})
    app.register_blueprint(api.blueprint)
    registries.load_registry_types()
    ma.init_app(app)
