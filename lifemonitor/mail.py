# Copyright (c) 2020-2021 CRS4
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
from datetime import datetime
from typing import List, Optional

from flask import Flask
from flask_mail import Mail, Message

from lifemonitor.auth.models import Notification

# set logger
logger = logging.getLogger(__name__)

# instantiate the mail class
mail = Mail()


def init_mail(app: Flask):
    mail_server = app.config.get('MAIL_SERVER', None)
    if mail_server:
        mail.init_app(app)
        logger.info("Mail service bound to server '%s'", mail_server)
        mail.disabled = False
        mail.webapp_url = app.config.get('WEBAPP_URL')
    else:
        mail.disabled = True


def send_notification(n: Notification, recipients: List[str]) -> Optional[datetime]:
    if mail.disabled:
        logger.info("Mail notifications are disabled")
    else:
        with mail.connect() as conn:
            logger.debug("Mail recipients for notification '%r': %r", n.id, recipients)
            if len(recipients) > 0:
                # FIXME: reformat mail subject
                msg = Message(
                    f'LifeMonitor notification: {n.type}',
                    bcc=recipients,
                    reply_to="noreply-lifemonitor@crs4.it"
                )
                # TODO: format body using a proper template
                msg.body = f"{n.id}<pre>{json.dumps(n.data)}</pre>"
                conn.send(msg)
                return datetime.utcnow()
    return None
