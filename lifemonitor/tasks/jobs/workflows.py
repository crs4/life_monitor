
import logging
import time

from flask import Response

from lifemonitor.api.controllers import workflows_post
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
        result = workflows_post(registration_data, async_processing=False, job=job)
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
