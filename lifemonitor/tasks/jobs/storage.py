
import logging

from lifemonitor.storage import RemoteStorage

from ..scheduler import TASK_EXPIRATION_TIME, schedule

# set module level logger
logger = logging.getLogger(__name__)

# initialize a RemoteStorage instance
storage: RemoteStorage = RemoteStorage()


@schedule(name='put_file', queue_name="storage", options={'max_retries': 0, 'max_age': TASK_EXPIRATION_TIME})
def put_file(bucket_name: str, local_path: str, remote_path: str):
    logger.debug("Event parameters: %r %r %r", bucket_name, local_path, remote_path)
    storage.put_file(local_path, remote_path)
