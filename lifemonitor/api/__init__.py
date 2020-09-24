import pathlib
import connexion
from .serializers import ma


def register_api(app, specs_dir):
    api = connexion.Api(pathlib.Path(specs_dir, 'api.yaml'),
                        validate_responses=True,
                        arguments={'global': 'global_value'})
    app.register_blueprint(api.blueprint)
    ma.init_app(app)
