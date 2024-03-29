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
from typing import List
from urllib.parse import urlparse

from flask_wtf import FlaskForm
from sqlalchemy.exc import IntegrityError
from wtforms import (BooleanField, HiddenField, PasswordField, SelectField,
                     SelectMultipleField, StringField)
from wtforms.validators import (URL, DataRequired, Email, EqualTo, Length,
                                Optional, ValidationError)

from lifemonitor.auth.oauth2.server.models import Client
from lifemonitor.utils import OpenApiSpecs

from .models import User, db

try:
    from wtforms import URLField
except ImportError:
    from wtforms.fields.html5 import URLField

# Set the module level logger
logger = logging.getLogger(__name__)


class LoginForm(FlaskForm):
    username = StringField(
        "Username", validators=[DataRequired(), Length(min=3, max=30)]
    )
    password = PasswordField("Password", validators=[DataRequired()])
    provider = HiddenField("Provider", validators=[Optional(), Length(min=3, max=30)])

    def get_user(self):
        user = User.query.filter_by(username=self.username.data).first()
        if not user:
            self.username.errors.append("Username not found")
            return None
        if not user.has_password:
            self.password.errors.append("The user has no password set")
            return None
        if not self.password.data or not user.verify_password(self.password.data):
            self.password.errors.append("Invalid password")
            return None
        return user


class UsernameValidator:
    regex = r"^[a-z0-9][a-z0-9\-_]+[a-z0-9]$"

    def __init__(self, banned: List[str] = None):
        self.banned = banned

    def __call__(self, form, field):
        return self.validate(field.data, self.banned)

    @classmethod
    def validate(cls, value: str, banned: List[str] = None) -> bool:
        value_length = len(value) if value else 0
        if value_length == 0:
            return ValidationError("Username cannot be empty")
        p = re.compile(cls.regex)
        if not re.search(p, value.lower()):
            raise ValidationError(
                "Please use only letters (a-zA-Z), numbers (0-9), "
                "hyphens (-), or underscores (_). "
                "Usernames cannot start or end with hyphens (-) or underscores (_)."
            )
        if banned and value.lower() in (word.lower() for word in banned):
            raise ValidationError("Username not allowed")
        return True


class RegisterForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(min=3, max=30),
            UsernameValidator(
                banned=["root", "admin", "sys", "administrator", "lifemonitor"]
            ),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=8, max=30),
            EqualTo("repeat_password", message="Passwords must match"),
        ],
    )
    repeat_password = PasswordField("Repeat Password")
    identity = HiddenField("identity")

    def create_user(self, identity=None):
        try:
            user = User(username=self.username.data) if not identity else identity.user
            if not identity:
                user.password = self.password.data
            elif identity.user_info.get("picture", None):
                user.picture = identity.user_info["picture"]
            user.username = self.username.data
            db.session.add(user)
            db.session.commit()
            return user
        except IntegrityError as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
            self.username.errors.append("This username is already taken")
            db.session.rollback()
            return None

    def validate(self, extra_validators=None):
        # if the current user has an external OAuth2 identity
        # then we do not validate the password field (which is optional)
        logger.debug(
            "OAuth identity: %r (%r)", self.identity.raw_data, not self.identity.data
        )
        if self.identity.data:
            return self.username.validate(self)
        return super().validate(extra_validators=extra_validators)


class SetPasswordForm(FlaskForm):
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=8, max=20),
            EqualTo("repeat_password", message="Passwords must match"),
        ],
    )
    repeat_password = PasswordField("Repeat Password")


class NotificationsForm(FlaskForm):
    enable_notifications = BooleanField(
        "enable_notifications",
        validators=[DataRequired()],
    )


class RedirectURIsValidator:
    def __call__(self, form, field):
        if not field.data:
            raise ValidationError("Redirect URI cannot be empty")
        uris = field.data.replace(" ", "")
        for uri in uris.split(","):
            if not self.validate_url(uri):
                raise ValidationError("Invalid Redirect URI '%s'" % uri)
        return True

    @staticmethod
    def validate_url(url):
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except ValueError:
            return False


class EmailForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[
            DataRequired(),
            Email(),
            EqualTo("repeat_email", message="email addresses do not match"),
        ],
    )
    repeat_email = StringField("Repeat Email")


class Oauth2ClientForm(FlaskForm):
    clientId = HiddenField("clientId")
    name = StringField("Client Name", validators=[DataRequired()])
    uri = URLField(
        "Client URI",
        validators=[
            DataRequired(message="Enter URI Please"),
            URL(require_tld=False, message="Enter Valid URI Please."),
        ],
    )

    redirect_uris = StringField(
        "Client Redirect URIs (one per line)",
        validators=[DataRequired(), RedirectURIsValidator()],
    )
    scopes = SelectMultipleField(
        "Allowed scopes",
        render_kw={"multiple": "multiple"},
        choices=[
            (k, v)
            for k, v in OpenApiSpecs.get_instance().authorization_code_scopes.items()
        ],
    )
    confidential = BooleanField("Confidential")
    auth_method = SelectField(
        "Client Authentication Method",
        choices=[
            ("client_secret_basic", "Authorization Header (client_secret_basic)"),
            ("client_secret_post", "Request Body (client_secret_post)"),
        ],
    )

    def get_client_data(self):
        logger.debug("Extracting client data from form...")
        data = {
            "name": self.name.data,
            "uri": self.uri.data,
            "redirect_uris": self.redirect_uris.data,
            "scopes": self.scopes.data,
            "confidential": self.confidential.data,
            "auth_method": self.auth_method.data if self.confidential.data else "none",
        }
        logger.debug("Client data: %r", data)
        return data

    def clear(self):
        self.clientId.data = None
        self.name.data = None
        self.uri.data = None
        self.redirect_uris.data = None
        self.scopes.data = None
        self.auth_method.data = "client_secret_post"
        self.confidential.data = False

    @staticmethod
    def from_object(client: Client) -> Oauth2ClientForm:
        form = Oauth2ClientForm()
        form.clientId.data = client.client_id
        form.name.data = client.client_name
        form.uri.data = client.client_uri
        form.redirect_uris.data = "\n".join(client.redirect_uris)
        form.scopes.data = client.scope
        form.auth_method.data = client.auth_method
        form.confidential.data = client.is_confidential()
        return form
