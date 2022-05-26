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
from typing import Dict, List

from flask import render_template
from flask_mail import Message
from lifemonitor.auth.models import (EventType, Notification, User,
                                     UserNotification)
from lifemonitor.db import db
from sqlalchemy.exc import InternalError


# set logger
logger = logging.getLogger(__name__)


class GithubWorkflowVersionNotification(Notification):

    __mapper_args__ = {
        'polymorphic_identity': 'github_workflow_version_notification'
    }
    
    @property
    def get_icon_path(self) -> str:
        return 'lifemonitor/static/img/logo/providers/github.png'

    def __init__(self, workflow_version: Dict, repository: Dict, action: str, users: List[User], extra_data: Dict = None) -> None:
        super().__init__(EventType.GITHUB_WORKFLOW_VERSION,
                         f"workflow {workflow_version['uuid']} version {workflow_version['version']['version']} {action}"
                         f"(source: {repository['full_name']}, ref: {repository['ref']})",
                         data={
                             'action': action,
                             'repository': repository,
                             'workflow_version': workflow_version
                         }, users=users)

    def to_mail_message(self, recipients: List[User]) -> Message:
        from lifemonitor.mail import mail
        try:
            wv = self.data.get('workflow_version', None)
            repo = self.data.get('repository', None)
            msg = Message(
                f'Github workflow version {self.data["action"]}: "{wv["name"]}" (ver. {wv["version"]["version"]})"',
                bcc=recipients,
                reply_to=self.reply_to
            )
            msg.html = render_template("mail/github_workflow_version_notification.j2",
                                       webapp_url=mail.webapp_url,
                                       workflow_version=wv, repository=repo,
                                       action=self.data["action"],
                                       json_data=self.data,
                                       logo=self.base64Logo, icon=self.encodeFile(self.get_icon_path))
            return msg
        except InternalError as e:
            logger.debug(e)
            db.session.rollback()

    @classmethod
    def find_by_user(cls, user: User) -> List[Notification]:
        return cls.query.join(UserNotification, UserNotification.notification_id == cls.id)\
            .filter(UserNotification.user_id == user.id).all()
