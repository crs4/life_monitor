
import datetime
import logging

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from lifemonitor.auth.models import (Notification,
                                     UnconfiguredEmailNotification, User)
from lifemonitor.mail import send_notification
from lifemonitor.tasks.scheduler import TASK_EXPIRATION_TIME, schedule

# set module level logger
logger = logging.getLogger(__name__)


logger.info("Importing task definitions")


@schedule(trigger=IntervalTrigger(seconds=30),
          queue_name="notifications", options={'max_retries': 0, 'max_age': TASK_EXPIRATION_TIME})
def send_email_notifications():
    notifications = [n for n in Notification.not_emailed()
                     if not isinstance(n, UnconfiguredEmailNotification)]
    logger.info("Found %r notifications to send by email", len(notifications))
    count = 0
    for n in notifications:
        logger.debug("Processing notification %r ...", n)
        recipients = [
            u.user.email for u in n.users
            if u.emailed is None and u.user.email_notifications_enabled and u.user.email
        ]
        sent = send_notification(n, recipients=recipients)
        logger.debug("Notification email sent: %r", sent is not None)
        if sent:
            logger.debug("Notification '%r' sent by email @ %r", n.id, sent)
            for u in n.users:
                if u.user.email in recipients:
                    u.emailed = sent
            n.save()
            count += 1
        logger.debug("Processing notification %r ... DONE", n)
    logger.info("%r notifications sent by email", count)
    return count


@schedule(trigger=CronTrigger(minute=0, hour=1),
          queue_name="notifications", options={'max_retries': 0, 'max_age': TASK_EXPIRATION_TIME})
def cleanup_notifications():
    logger.info("Starting notification cleanup")
    count = 0
    current_time = datetime.datetime.utcnow()
    one_week_ago = current_time - datetime.timedelta(days=0)
    notifications = Notification.older_than(one_week_ago)
    for n in notifications:
        try:
            n.delete()
            count += 1
        except Exception as e:
            logger.debug(e)
            logger.error("Error when deleting notification %r", n)
    logger.info("Notification cleanup completed: deleted %r notifications", count)


@schedule(trigger=IntervalTrigger(seconds=60),
          queue_name="notifications", options={'max_retries': 0, 'max_age': TASK_EXPIRATION_TIME})
def check_email_configuration():
    logger.info("Check for users without notification email")
    users = []
    try:
        for u in User.all():
            n_list = UnconfiguredEmailNotification.find_by_user(u)
            if not u.email:
                if len(n_list) == 0:
                    users.append(u)
            elif len(n_list) > 0:
                for n in n_list:
                    n.remove_user(u)
                u.save()
        if len(users) > 0:
            n = UnconfiguredEmailNotification(
                "Unconfigured email",
                users=users)
            n.save()
    except Exception as e:
        logger.debug(e)
    logger.info("Check for users without notification email configured: generated a notification for users %r", users)
