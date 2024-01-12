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
from unittest.mock import patch

from lifemonitor.auth.models import Notification, User, UserNotification

logger = logging.getLogger(__name__)


@patch("lifemonitor.mail.mail")
def test_unconfigured_email_notification(mail, app_settings, app_context, user1):
    logger.debug("App settings: %r", app_settings)
    app = app_context.app
    logger.debug("App: %r", app)
    config = app.config
    logger.debug("Config: %r", config)
    logger.debug(user1)

    # get a reference to the current user
    user: User = user1['user']

    # No notification should exist
    notifications = Notification.all()
    logger.debug("Notifications before check: %r", notifications)
    assert len(notifications) == 0, "Unexpected number of notifications"

    # Check email configuration
    from lifemonitor.tasks.jobs.notifications import check_email_configuration, send_email_notifications
    check_email_configuration()

    # Check if notification for user1 and admin has been generated
    notifications = Notification.all()
    logger.debug("Notifications after check: %r", notifications)
    assert len(notifications) == 1, "Unexpected number of notifications"

    n: Notification = notifications[0]
    un: UserNotification = next((_.user for _ in n.users if _.user_id == user.id), None)
    assert un is not None, "User1 should be notified"

    # no additional notification should be generated
    check_email_configuration()
    notifications = Notification.all()
    logger.debug("Notifications after check: %r", notifications)
    assert len(notifications) == 1, "No additional notification should be generated"

    # try to send notifications via email
    # no email should be sent beacause the user has no configured email
    sent_notifications = send_email_notifications()
    assert sent_notifications == 0, "Unexpected number of sent notifications"

    # update and validate user email
    user.email = "user1@lifemonitor.eu"
    user.verify_email(user.email_verification_code)
    user.enable_email_notifications()
    user.save()

    # try to send notifications via email
    mail.disabled = False
    mail.connect.return_value.__enter__.return_value.name = "TempContext"
    sent_notifications = send_email_notifications()
    mail.connect.assert_not_called()
    assert sent_notifications == 0, "Unexpected number of sent notifications"
