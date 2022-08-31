import logging
import os
from typing import List

from lifemonitor.utils import load_modules

# set module level logger
logger = logging.getLogger(__name__)


def load_job_modules(include: List[str] = None, exclude: List[str] = None):
    __job_modules__ = load_modules(os.path.dirname(__file__), include=include, exclude=exclude)
    logger.debug("Loaded job modules: %r", __job_modules__)
    return __job_modules__


__all__ = ["load_job_modules"]
