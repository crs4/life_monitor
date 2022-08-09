
import logging

from ..app import create_app
from ..tasks import load_task_jobs

logger = logging.getLogger(__name__)


app = create_app(worker=True, load_jobs=False)
app.app_context().push()
load_task_jobs()

broker = app.broker
