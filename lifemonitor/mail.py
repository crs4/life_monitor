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


import logging
from datetime import datetime
from typing import List, Optional

from flask import Flask, render_template
from flask_mail import Mail, Message
from sqlalchemy.exc import InternalError

from lifemonitor.api.models import TestInstance
from lifemonitor.auth.models import Notification, User
from lifemonitor.db import db
from lifemonitor.utils import Base64Encoder, get_external_server_url

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


def send_email_validation_message(user: User):
    if mail.disabled:
        logger.info("Mail notifications are disabled")
    if user is None or user.is_anonymous:
        logger.warning("An authenticated user is required")
    with mail.connect() as conn:
        confirmation_address = f"{get_external_server_url()}/validate_email?code={user.email_verification_code}"
        logo = Base64Encoder.encode_file('lifemonitor/static/img/logo/lm/LifeMonitorLogo.png')
        msg = Message(
            f'Confirm your email address',
            recipients=[user.email],
            reply_to="noreply-lifemonitor@crs4.it"
        )
        msg.html = render_template("mail/validate_email.j2",
                                   confirmation_address=confirmation_address, user=user, logo=logo)
        conn.send(msg)


def send_notification(n: Notification, recipients: List[str]) -> Optional[datetime]:
    if mail.disabled:
        logger.info("Mail notifications are disabled")
    else:
        with mail.connect() as conn:
            logger.debug("Mail recipients for notification '%r': %r", n.id, recipients)
            if len(recipients) > 0:
                build_data = n.data['build']
                try:
                    i = TestInstance.find_by_uuid(build_data['instance']['uuid'])
                    if i is not None:
                        wv = i.test_suite.workflow_version
                        b = i.last_test_build
                        suite = i.test_suite
                        logo = Base64Encoder.encode_file('lifemonitor/static/img/logo/lm/LifeMonitorLogo.png')
                        icon = Base64Encoder.encode_file('lifemonitor/static/img/icons/times-circle-solid.svg')
                        suite.url_param = Base64Encoder.encode_object({
                            'workflow': str(wv.workflow.uuid),
                            'suite': str(suite.uuid)
                        })
                        msg = Message(
                            f'Workflow "{wv.name} ({wv.version})": some builds were not successful',
                            bcc=recipients,
                            reply_to="noreply-lifemonitor@crs4.it"
                        )
                        msg.html = render_template("mail/build_failure_notification.j2",
                                                   webapp_url=mail.webapp_url,
                                                   workflow_version=wv, build=b,
                                                   test_instance=i,
                                                   suite=suite,
                                                   json_data=build_data,
                                                   logo=logo, icon=icon)
                        conn.send(msg)
                        return datetime.utcnow()
                except InternalError as e:
                    logger.debug(e)
                    db.session.rollback()
    return None
