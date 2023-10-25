import datetime
import logging
from typing import Dict

import dramatiq
import flask
from apscheduler import events
from apscheduler.triggers.date import DateTrigger
from flask_apscheduler import APScheduler

# set module level logger
logger = logging.getLogger(__name__)


# set expiration time (in msec) of tasks
TASK_EXPIRATION_TIME = 30000


class Scheduler(APScheduler):

    def __init__(self, scheduler=None, app=None):
        super().__init__(scheduler, app)
        self._not_scheduled_jobs: Dict[str, dramatiq.Actor] = {}
        if logger.isEnabledFor(logging.DEBUG):
            self.add_listener(self._on_event)

    def _on_event(self, event: events.JobEvent):
        logger.debug("Event: %r", event)
        logger.debug("List of current jobs: %r", self.get_jobs())
        logger.debug("List of deferred jobs: %r", self._not_scheduled_jobs)
        if event.code in [events.EVENT_JOB_EXECUTED, events.EVENT_JOB_ERROR]:
            logger.debug("List of current jobs: %r", self.get_jobs())

    @staticmethod
    def __enqueue_dramatiq_job__(**message):
        broker = dramatiq.get_broker()
        broker.enqueue(dramatiq.Message(**message))

    def get_scheduled_jobs(self):
        return self._jobs

    def add_deferred_job(self, job_name: str, actor: dramatiq.Actor):
        self._not_scheduled_jobs[job_name] = actor

    def remove_deferred_job(self, job_name: str):
        return self._not_scheduled_jobs.pop(job_name, None)

    def get_deferred_job(self, job_name: str) -> dramatiq.Actor:
        return self._not_scheduled_jobs.get(job_name, None)

    def get_deferred_jobs(self) -> Dict[str, dramatiq.Actor]:
        return self._not_scheduled_jobs.copy()

    def run_job(self, job_name: str, *args, trigger=None, **kwargs):
        actor = self.get_deferred_job(job_name)
        assert actor, f"Job '{job_name}' not found"
        self.add_job(id=job_name, name=job_name, func=actor.send, args=args, kwargs=kwargs,
                     trigger=trigger or DateTrigger(run_date=datetime.datetime.now()), replace_existing=True)


def schedule(trigger=None, name=None, priority=0, queue_name: str = "default", options: Dict = None):
    """
    Decorator to add a scheduled job calling the wrapped function.
    :param  trigger:  an instance of any of the trigger types provided in apscheduler.triggers.
    """
    def decorator(fn):
        # Set the current app
        app = flask.current_app
        assert app, "No Flask App found in the current context"

        # Set fn_name
        fn_name = f"{fn.__module__}.{fn.__name__}"

        # Define the job name
        job_name = name or fn_name
        # create an actor for 'fn'
        aoptions = options or {}
        actor = dramatiq.actor(fn, actor_name=job_name, queue_name=queue_name, priority=priority, broker=None, **aoptions)

        # We check to see whether the scheduler is available simply by verifying whether the
        # app has the `scheduler` attributed defined.
        # The LM app should have this; the worker app does not have it.
        if hasattr(app, "scheduler"):
            scheduler: Scheduler = app.scheduler

            # Register scheduled or deferred jobs
            if trigger:
                logger.debug("Scheduling function %s with trigger %r", fn_name, trigger)
                scheduler.add_job(id=fn_name, name=job_name, func=actor.send, trigger=trigger, replace_existing=True)
            else:
                logger.debug("Registering deferred job for function %s", fn_name)
                scheduler.add_deferred_job(job_name, actor)
        else:
            logger.debug("Schedule %s no-op - scheduler not initialized", fn_name)
        return fn
    return decorator
