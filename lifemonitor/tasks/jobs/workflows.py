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
import time

from flask import Response

from lifemonitor.api.controllers import process_workflows_post
from lifemonitor.exceptions import report_problem_from_exception

from ..models import Job
from ..scheduler import TASK_EXPIRATION_TIME, schedule

# set module level logger
logger = logging.getLogger(__name__)


@schedule(name='register_workflow', queue_name="workflows", options={'max_retries': 0, 'max_age': TASK_EXPIRATION_TIME})
def register_workflow(job_id: str, registration_data: object):
    logger.debug("Event parameters: %r", registration_data)
    # get job
    job = Job.get_job(job_id)
    # update status
    job.update_status("registration started", True)
    time.sleep(2)
    # start registration
    try:
        result = process_workflows_post(registration_data, async_processing=False, job=job)
    except Exception as e:
        logger.exception(e)
        result = report_problem_from_exception(e)
    # notify result
    time.sleep(2)
    if isinstance(result, Response):
        job.update_data({'error': result.get_json()}, save=False)
        job.update_status("error", save=True)
    else:
        job.update_status('completed', save=False)
        job.update_data({'result': result})
