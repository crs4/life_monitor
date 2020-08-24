import pathlib
import connexion


def register_api(app, specs_dir):
    api = connexion.Api(pathlib.Path(specs_dir, 'api.yaml'),
                        arguments={'global': 'global_value'})
    app.register_blueprint(api.blueprint)
