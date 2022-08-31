
import logging

from apscheduler.triggers.cron import CronTrigger
from lifemonitor.tasks.scheduler import TASK_EXPIRATION_TIME, schedule

# set module level logger
logger = logging.getLogger(__name__)


logger.info("Importing task definitions")


@schedule(trigger=CronTrigger(second=0), queue_name="heartbeat",
          options={'max_retries': 3, 'max_age': TASK_EXPIRATION_TIME})
def heartbeat():
    logger.info("Heartbeat!")
