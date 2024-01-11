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


from __future__ import annotations

import logging
import re

from flask_wtf import FlaskForm
from lifemonitor.auth.models import User
from wtforms import BooleanField, StringField, HiddenField
from wtforms.validators import AnyOf, ValidationError
from lifemonitor.api import models

from .settings import GithubUserSettings

# Set the module level logger
logger = logging.getLogger(__name__)


class BranchAndTagNameValidator:
    regex = r"^([^a-zA-Z0-9]+[\w\-./]*)|([\w\-./]*[^a-zA-Z0-9\-_]+)$"
    base_message = (
        "Invalid characters detected. "
        "Use letters (both uppercase and lowercase), numbers, hyphens, and underscores. "
        "Avoid using special characters, spaces, or symbols in branch and tag names."
    )
    message = base_message + "Branches cannot start or end with hyphens or underscores."

    def __init__(self, message: str = None):
        if message:
            self.message = message

    def __call__(self, form, field):
        return self.validate(field.data, self.message)

    @classmethod
    def validate(cls, value: str, message: str) -> bool:
        logger.warning("Validating: %r", value)
        if not value:
            return True
        p = re.compile(cls.regex)
        for name in re.split(r",\s*", value):
            if re.search(p, name.lower()):
                logger.error("%r is not valid", name)
                raise ValidationError(message)
            logger.warning("%r is valid", name)
        return True


class RegistryNameValidator:
    available_registries = [w.name for w in models.WorkflowRegistry.all()]

    def __call__(self, form, field):
        return self.validate(field.data)

    @classmethod
    def validate(cls, value: str) -> bool:
        logger.warning("Validating: %r", value)
        if not value:
            return True
        for name in re.split(r",\s*", value):
            if name not in cls.available_registries:
                logger.error("%r is not valid", name)
                raise ValidationError(
                    "'{}' is not a valid registry name. Available registries are: {}".format(
                        name, ", ".join(cls.available_registries)
                    )
                )
            logger.warning("%r is valid", name)
        return True


class GithubSettingsForm(FlaskForm):
    branches = StringField(
        "branches",
        description="List of comma-separated branches (e.g., master, develop, feature/123)",
        validators=[
            BranchAndTagNameValidator(
                message=f"{BranchAndTagNameValidator.base_message} "
                "Branches cannot start or end with hyphens or underscores."
            )
        ],
    )
    tags = StringField(
        "tags",
        description="List of comma-separated tags (e.g., v*, v*.*.*, release-v*)",
        validators=[
            BranchAndTagNameValidator(
                message=f"{BranchAndTagNameValidator.base_message} "
                "Tags cannot start or end with hyphens or underscores."
            )
        ],
    )
    all_branches = BooleanField("all_branches", validators=[AnyOf([True, False])])
    all_tags = BooleanField("all_tags", validators=[AnyOf([True, False])])
    check_issues = BooleanField("check_issues", validators=[AnyOf([True, False])])

    registries = HiddenField(
        "registries",
        description="",
    )

    available_registries = models.WorkflowRegistry.all()

    def update_model(self, user: User) -> GithubUserSettings:
        assert user and not user.is_anonymous, user
        settings = (
            GithubUserSettings(user)
            if not user.github_settings
            else user.github_settings
        )
        settings.all_branches = self.all_branches.data
        settings.all_tags = self.all_tags.data
        settings.check_issues = self.check_issues.data
        settings.branches = (
            [_.strip() for _ in self.branches.data.split(",")]
            if self.branches.data
            else []
        )
        settings.tags = (
            [_.strip() for _ in self.tags.data.split(",")] if self.tags.data else []
        )
        return settings

    @classmethod
    def from_model(cls, user: User) -> GithubSettingsForm:
        if user.is_anonymous:
            return None
        settings = (
            GithubUserSettings(user)
            if not user.github_settings
            else user.github_settings
        )
        form = cls()
        form.all_branches.data = settings.all_branches
        form.all_tags.data = settings.all_tags
        form.branches.data = ", ".join(settings.branches)
        form.tags.data = ", ".join(settings.tags)
        form.check_issues.data = settings.check_issues
        return form
