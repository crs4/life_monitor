
import logging

from ..app import create_app

logger = logging.getLogger(__name__)

app = create_app(worker=True, load_jobs=True)
app.app_context().push()

# check if the app is in maintenance mode
if app.config.get("MAINTENANCE_MODE", False):
    logger.warning("Application is in maintenance mode")
    app.run()
else:
    # initialise the message broker
    broker = app.broker
