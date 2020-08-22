def register_commands(app):
    # register DB commands
    from .db import blueprint
    app.register_blueprint(blueprint)
    from .api_key import blueprint as api_keys
    app.register_blueprint(api_keys)
