import logging
from .providers.github import blueprint as github_blueprint

# Config a module level logger
logger = logging.getLogger(__name__)


def register_api(app, specs_dir):
    app.register_blueprint(github_blueprint, url_prefix="/login")
