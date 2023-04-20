from __future__ import annotations

import logging
from datetime import datetime

from flask import Flask
from git import List

from lifemonitor.exceptions import EntityNotFoundException
from lifemonitor.tasks.scheduler import Scheduler

from .utils import get_job_data, make_job_id, notify_update, set_job_data


class JobNotFound(EntityNotFoundException):
    pass


class Job:

    # Config a module level logger
    logger = logging.getLogger(__name__)

    def __init__(self, job_id: str = None,
                 job_type: str = None,
                 listening_ids: List[str] = None,
                 listening_rooms: List[str] = None,
                 data: object = None,
                 status: str = None) -> None:
        self._job_id = job_id or make_job_id()
        self._data = data or {}
        self._data['job_id'] = self._job_id
        if listening_ids:
            self._data['listening_ids'] = listening_ids
        if listening_rooms:
            self._data['listening_rooms'] = listening_rooms
        if job_type:
            self._data['type'] = job_type
        if status:
            self._data['status'] = status
        if not self._data.get('status', None):
            self._data['status'] = 'created'

    @property
    def id(self) -> str:
        return self._job_id

    @property
    def type(self) -> str:
        return self._data['type']

    @property
    def data(self) -> object:
        return self._data.copy()

    @property
    def listening_ids(self) -> List[str]:
        return self._data.get('listening_ids', None)

    @property
    def listening_rooms(self) -> List[str]:
        return self._data.get('listening_rooms', None)

    def update_data(self, data: object, save: bool = False):
        self._data.update(data)
        if save:
            self.save()

    def update_status(self, status, save: bool = False):
        self._data['status'] = status
        if save:
            self.save()

    def save(self):
        if not self._data.get('created', None):
            self._data['created'] = datetime.utcnow().timestamp()  # .replace(tzinfo=timezone.utc).timestamp()
        self._data['modified'] = datetime.utcnow().timestamp()
        set_job_data(self._job_id, self._data)
        notify_update(self._job_id, target_ids=self.listening_ids, target_rooms=self.listening_rooms)

    def load(self):
        self._data = get_job_data(self._job_id)

    def submit(self, app: Flask, as_job_name: str = None):
        scheduler: Scheduler = app.scheduler
        self.logger.debug("Current app scheduler: %r", scheduler)
        scheduler.run_job(as_job_name or self.type, self.id, self._data.get('data', None))

    @classmethod
    def get_job(cls, job_id: str) -> Job:
        job_data = get_job_data(job_id)
        if not job_data:
            raise JobNotFound(Job, entity_id=job_id)
        return Job(job_id=job_id, data=job_data)
