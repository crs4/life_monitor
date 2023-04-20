import json

import logging

from git import List
from lifemonitor.cache import cache

logger = logging.getLogger(__name__)

JOB_CACHE_TIMEOUT = 60


def make_job_id() -> str:
    from uuid import uuid4
    return str(uuid4())


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
