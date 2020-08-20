import logging
from .providers.github import blueprint as github_blueprint
from .providers.seek import blueprint as seek_blueprint

# Config a module level logger
logger = logging.getLogger(__name__)


def register_api(app, specs_dir):
    app.register_blueprint(seek_blueprint, url_prefix="/login")
    app.register_blueprint(github_blueprint, url_prefix="/login")
