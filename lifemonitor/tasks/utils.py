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

import json

import logging

from git import List
from lifemonitor.cache import cache

logger = logging.getLogger(__name__)

JOB_CACHE_TIMEOUT = 60


def make_job_id() -> str:
    from uuid import uuid4
    return str(uuid4())


def validate_job_id(job_id: str) -> bool:
    '''Validate the job id defined as uuid4'''
    from uuid import UUID
    try:
        UUID(job_id, version=4)
        return True
    except ValueError:
        return False


def get_job_key(job_id: str):
    return f"job-{job_id}"


def set_job_data(job_id: str, data: object, job_key: str = None) -> object:
    job_key = job_key or get_job_key(job_id=job_id)
    job_data = get_job_data(job_id=job_id, job_key=job_key)
    if job_data:
        job_data.update(data)
    else:
        job_data = data
    cache.set(job_key, json.dumps(job_data), timeout=JOB_CACHE_TIMEOUT)
    return job_data


def get_job_data(job_id: str, job_key: str = None) -> object:
    job_key = job_key or get_job_key(job_id=job_id)
    serialized_job_data = cache.get(job_key)
    if not serialized_job_data:
        return None
    return json.loads(serialized_job_data)


def notify_update(job_id: str, type: str = 'jobUpdate',
                  target_ids: List[str] = None, target_rooms: List[str] = None,
                  delay: int = 0):
    from lifemonitor.ws import io
    job = get_job_data(job_id)
    if not job:
        logger.warning(f"Job {job_id} not found")
    else:
        io.publish_message({
            "type": type,
            "data": job,
        }, target_ids=target_ids, target_rooms=target_rooms, delay=delay)
