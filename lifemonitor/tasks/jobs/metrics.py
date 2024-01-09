# Copyright (c) 2020-2024 CRS4
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

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
