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
from typing import List

from flask import render_template
from flask_mail import Message
from lifemonitor.auth.models import (EventType, Notification, User,
                                     UserNotification)
from lifemonitor.db import db
from lifemonitor.utils import Base64Encoder
from sqlalchemy.exc import InternalError

from . import TestInstance

# set logger
logger = logging.getLogger(__name__)


class WorkflowStatusNotification(Notification):

    __mapper_args__ = {
        'polymorphic_identity': 'workflow_status_notification'
    }

    def get_icon_path(self) -> str:
        return 'lifemonitor/static/img/icons/' \
            + ('times-circle-solid.svg'
               if self.event == EventType.BUILD_FAILED else 'check-circle-solid.svg')

    def to_mail_message(self, recipients: List[User]) -> Message:
        from lifemonitor.mail import mail
        build_data = self.data['build']
        try:
            i = TestInstance.find_by_uuid(build_data['instance']['uuid'])
            if i is not None:
                wv = i.test_suite.workflow_version
                b = i.get_test_build(build_data['build_id'])
                suite = i.test_suite
                suite.url_param = Base64Encoder.encode_object({
                    'workflow': str(wv.workflow.uuid),
                    'suite': str(suite.uuid)
                })
                instance_status = "is failing" \
                    if self.event == EventType.BUILD_FAILED else "has recovered"
                msg = Message(
                    f'Workflow "{wv.name} ({wv.version})": test instance {i.name} {instance_status}',
                    bcc=recipients,
                    reply_to=self.reply_to
                )
                msg.html = render_template("mail/instance_status_notification.j2",
                                           webapp_url=mail.webapp_url,
                                           workflow_version=wv, build=b,
                                           test_instance=i,
                                           suite=suite,
                                           json_data=build_data,
                                           logo=self.base64Logo, icon=self.encodeFile(self.get_icon_path))
                return msg
        except InternalError as e:
            logger.debug(e)
            db.session.rollback()

    @classmethod
    def find_by_user(cls, user: User) -> List[Notification]:
        return cls.query.join(UserNotification, UserNotification.notification_id == cls.id)\
            .filter(UserNotification.user_id == user.id).all()
