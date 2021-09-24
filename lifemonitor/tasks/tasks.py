
import logging

import dramatiq

# set module level logger
logger = logging.getLogger(__name__)


@dramatiq.actor(max_retries=2, store_results=True)
def add(x, y):
    r = int(x) + int(y)
    logger.info("The <add> actor.  The sum of %s and %s = %s", x, y, r)
    return r
