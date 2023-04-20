
import logging

from apscheduler.triggers.interval import IntervalTrigger
from lifemonitor.tasks.scheduler import TASK_EXPIRATION_TIME, schedule
from lifemonitor.metrics.services import update_stats

# set module level logger
logger = logging.getLogger(__name__)


logger.info("Importing task definitions")


@schedule(trigger=IntervalTrigger(seconds=30), queue_name="metrics",
          options={'max_retries': 3, 'max_age': TASK_EXPIRATION_TIME})
def update_metrics():
    logger.info("Updating metrics...")
    update_stats()
    logger.info("Metrics updated!")
