import logging

from authlib.integrations.flask_client import OAuth

# Config a module level logger
logger = logging.getLogger(__name__)

# Create an instance of OAuth registry for oauth clients.
oauth2_registry = OAuth()
