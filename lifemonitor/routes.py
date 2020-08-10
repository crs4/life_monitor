def register_routes(app, specs_dir="./specs"):
    """
    Register routes of the flask app

    :param app: a Flask application instance
    :param specs_dir: path to the specs folder
    :return:
    """
    from .api import register_api

    register_api(app, specs_dir)
