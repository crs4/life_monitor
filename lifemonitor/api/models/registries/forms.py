# Copyright (c) 2020-2022 CRS4
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


from __future__ import annotations

import logging

from flask_wtf import FlaskForm
from lifemonitor.auth import User
from wtforms import HiddenField

from .settings import RegistrySettings

# Set the module level logger
logger = logging.getLogger(__name__)


def __get_registries__():
    from .registry import WorkflowRegistry
    return WorkflowRegistry.all()


class RegistrySettingsForm(FlaskForm):

    action = HiddenField("action", description="")
    registry = HiddenField("registry", description="")
    registries = HiddenField("registries", description="")

    available_registries = None

    def update_model(self, user: User):
        assert user and not user.is_anonymous, user
        settings = user.registry_settings
        settings.registries = [_.strip() for _ in self.registries.data.split(',')] if self.registries.data else []
        return settings

    @classmethod
    def from_model(cls, user: User) -> RegistrySettings:
        if user.is_anonymous:
            return None
        settings = user.registry_settings
        form = cls()
        form.registries.data = ','.join(settings.registries)
        form.available_registries = __get_registries__()
        return form
