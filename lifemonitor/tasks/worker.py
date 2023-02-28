
import logging

from ..app import create_app

logger = logging.getLogger(__name__)


app = create_app(worker=True, load_jobs=True)
app.app_context().push()
init_task_jobs()

broker = app.broker
