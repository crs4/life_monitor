def register_commands(app):
    # register DB commands
    from .db import blueprint
    app.register_blueprint(blueprint)
