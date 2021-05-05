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

from __future__ import annotations

import copy
import logging
import time
from datetime import datetime
from typing import List

from authlib import oidc
from authlib.integrations.flask_oauth2 import \
    AuthorizationServer as OAuth2AuthorizationServer
from authlib.integrations.sqla_oauth2 import (OAuth2AuthorizationCodeMixin,
                                              OAuth2ClientMixin,
                                              OAuth2TokenMixin,
                                              create_query_client_func,
                                              create_save_token_func)
from authlib.oauth2.rfc6749 import InvalidRequestError, grants
from authlib.oauth2.rfc7636 import CodeChallenge
from flask import current_app
from lifemonitor.auth.models import User
from lifemonitor.db import db
from lifemonitor.models import ModelMixin
from lifemonitor.utils import get_base_url, values_as_list, values_as_string
from werkzeug.security import gen_salt

# Set the module level logger
logger = logging.getLogger(__name__)


class Client(db.Model, OAuth2ClientMixin):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(48), index=True, unique=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey('user.id', ondelete='CASCADE')
    )
    user = db.relationship(
        'User',
        backref=db.backref(
            "clients",
            cascade="all, delete-orphan",
        ),
    )

    __tablename__ = "oauth2_client"

    def is_confidential(self):
        return self.has_client_secret()

    def set_client_metadata(self, value):
        if not isinstance(value, dict):
            return
        data = copy.deepcopy(value)
        data['scope'] = values_as_string(value['scope'], out_separator=" ")
        for p in ('redirect_uris', 'grant_types', 'response_types', 'contacts'):
            data[p] = values_as_list(value.get(p, []))
        return super().set_client_metadata(data)

    @property
    def redirect_uris(self):
        return super().redirect_uris

    @redirect_uris.setter
    def redirect_uris(self, value):
        metadata = self.client_metadata
        metadata['redirect_uris'] = value
        self.set_client_metadata(metadata)

    @property
    def scopes(self):
        return self.scope.split(" ") if self.scope else []

    @scopes.setter
    def scopes(self, scopes):
        metadata = self.client_metadata
        metadata['scope'] = scopes
        self.set_client_metadata(metadata)

    @property
    def auth_method(self):
        return self.client_metadata.get('token_endpoint_auth_method')

    @auth_method.setter
    def auth_method(self, value):
        metadata = self.client_metadata
        metadata['token_endpoint_auth_method'] = value
        self.set_client_metadata(metadata)

    @classmethod
    def find_by_id(cls, client_id) -> Client:
        return cls.query.get(client_id)

    @classmethod
    def all(cls) -> List[Client]:
        return cls.query.all()


class Token(db.Model, ModelMixin, OAuth2TokenMixin):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey('user.id', ondelete='CASCADE')
    )
    user = db.relationship('User')
    client_id = db.Column(db.String,
                          db.ForeignKey('oauth2_client.client_id', ondelete='CASCADE'))
    client = db.relationship('Client')

    __tablename__ = "oauth2_client_token"

    def is_expired(self) -> bool:
        return self.check_token_expiration(self.expires_at)

    def is_refresh_token_valid(self) -> bool:
        return self if not self.revoked else None

    @property
    def expires_at(self):
        return self.issued_at + self.expires_in

    @classmethod
    def find(cls, access_token):
        return cls.query.filter(Token.access_token == access_token).first()

    @classmethod
    def find_by_user(cls, user: User) -> List[Token]:
        return cls.query.filter(Token.user == user).all()

    @classmethod
    def all(cls) -> List[Token]:
        return cls.query.all()

    @staticmethod
    def check_token_expiration(expires_at) -> bool:
        return datetime.utcnow().timestamp() - expires_at > 0


class AuthorizationServer(OAuth2AuthorizationServer):

    def __init__(self, app=None):
        super().__init__(app,
                         query_client=create_query_client_func(db.session, Client),
                         save_token=create_save_token_func(db.session, Token))
        # register it to grant endpoint
        self.register_grant(AuthorizationCodeGrant, [
            OpenIDCode(require_nonce=True),
            CodeChallenge(required=True)
        ])
        # register it to grant endpoint
        self.register_grant(grants.ImplicitGrant)
        # register it to grant endpoint
        self.register_grant(PasswordGrant)
        # register it to grant endpoint
        self.register_grant(ClientCredentialsGrant)
        # register it to grant endpoint
        self.register_grant(RefreshTokenGrant)

    @classmethod
    def create_client(cls, user,
                      client_name, client_uri,
                      grant_type, response_type, scope,
                      redirect_uri,
                      token_endpoint_auth_method=None, commit=True):
        logger.debug("SCOPE: %r", scope)
        client_id = gen_salt(24)
        client_id_issued_at = int(time.time())
        client = Client(
            client_id=client_id,
            client_id_issued_at=client_id_issued_at,
            user_id=user.id,
        )

        return cls.update_client(
            user, client,
            client_name, client_uri,
            grant_type, response_type, scope,
            redirect_uri,
            token_endpoint_auth_method=token_endpoint_auth_method, commit=commit
        )

    @classmethod
    def update_client(cls, user: User, client: Client,
                      client_name, client_uri,
                      grant_type, response_type, scope,
                      redirect_uri,
                      token_endpoint_auth_method=None, commit=True):

        if client.user_id != user.id:
            raise ValueError("Invalid user!")

        client_metadata = {
            "client_name": client_name,
            "client_uri": client_uri,
            "grant_types": grant_type,
            "redirect_uris": redirect_uri,
            "response_types": response_type,
            "scope": scope,
            "token_endpoint_auth_method": token_endpoint_auth_method
        }
        client.set_client_metadata(client_metadata)

        if token_endpoint_auth_method == 'none':
            client.client_secret = ''
        elif not client.client_secret:
            client.client_secret = gen_salt(48)

        if commit:
            db.session.add(client)
            db.session.commit()
        return client

    @staticmethod
    def request_authorization(client: Client, user: User) -> bool:
        # We want to skip request for permssion when the client is a workflow registry.
        # The current implementation supports only workflow registries as
        # client_credentials clients. Thus, we can simple check if the grant 'client_credentials'
        # has been assigned to the client
        if client.check_grant_type("client_credentials"):
            return False
        for t in Token.find_by_user(user):
            if not t.revoked and not t.is_expired():
                return False
        return True

    @staticmethod
    def get_client(user: User, clientId):
        return next((c for c in user.clients if c.client_id == clientId), None)

    @classmethod
    def delete_client(cls, user: User, clientId):
        client = cls.get_client(user, clientId)
        if not client:
            return False
        db.session.delete(client)
        db.session.commit()
        return True


class AuthorizationCode(db.Model, OAuth2AuthorizationCodeMixin):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey('user.id', ondelete='CASCADE')
    )
    user = db.relationship('User')


class AuthorizationCodeGrant(grants.AuthorizationCodeGrant):
    TOKEN_ENDPOINT_AUTH_METHODS = [
        'client_secret_basic', 'client_secret_post', 'none'
    ]

    def save_authorization_code(self, code, request):
        auth_code = AuthorizationCode(
            code=code,
            client_id=request.client.client_id,
            redirect_uri=request.redirect_uri,
            scope=request.scope,
            user_id=request.user.id,
            # openid request MAY have "nonce" parameter
            nonce=request.data.get('nonce', None),
            # PKCE authentication method
            code_challenge=request.data.get('code_challenge', None),
            code_challenge_method=request.data.get('code_challenge_method', None)
        )
        db.session.add(auth_code)
        db.session.commit()
        return auth_code

    def query_authorization_code(self, code, client):
        return AuthorizationCode.query.filter_by(
            code=code, client_id=client.client_id).first()

    def delete_authorization_code(self, authorization_code):
        db.session.delete(authorization_code)
        db.session.commit()

    def authenticate_user(self, authorization_code):
        return User.query.get(authorization_code.user_id)


class PasswordGrant(grants.ResourceOwnerPasswordCredentialsGrant):
    TOKEN_ENDPOINT_AUTH_METHODS = [
        'client_secret_basic', 'client_secret_post'
    ]

    def authenticate_user(self, username, password):
        user = User.query.filter_by(username=username).first()
        if not user:
            raise InvalidRequestError("Username {} not found".format(username))
        if not user.check_password(password):
            raise InvalidRequestError("Password not valid!")
        return user


class ClientCredentialsGrant(grants.ClientCredentialsGrant):
    TOKEN_ENDPOINT_AUTH_METHODS = [
        'client_secret_basic', 'client_secret_post'
    ]


class RefreshTokenGrant(grants.RefreshTokenGrant):
    TOKEN_ENDPOINT_AUTH_METHODS = [
        'client_secret_basic', 'client_secret_post'
    ]
    INCLUDE_NEW_REFRESH_TOKEN = True

    def authenticate_refresh_token(self, refresh_token):
        item = Token.query.filter_by(refresh_token=refresh_token).first()
        # define is_refresh_token_valid by yourself
        # usually, you should check if refresh token is expired and revoked
        return item and item.is_refresh_token_valid()

    def authenticate_user(self, credential):
        return User.query.get(credential.user_id)

    def revoke_old_credential(self, credential):
        credential.revoked = True
        db.session.add(credential)
        db.session.commit()


class OpenIDCode(oidc.core.grants.OpenIDCode):

    __jwt_secret_key__ = None

    def exists_nonce(self, nonce, request):
        exists = AuthorizationCode.query.filter_by(
            client_id=request.client_id, nonce=nonce
        ).first()
        return bool(exists)

    def get_jwt_config(self, grant):
        return {
            'key': self.get_jwt_key(),
            'alg': 'RS512',
            'iss': get_base_url(),
            'exp': current_app.config.get('JWT_EXPIRATION_TIME')
        }

    def generate_user_info(self, user, scope):
        user_info = oidc.core.UserInfo(sub=user.id, name=user.username)
        # if 'email' in scope:
        #     user_info['email'] = user.email
        return user_info

    @classmethod
    def get_jwt_key(cls):
        if cls.__jwt_secret_key__ is None:
            with open(current_app.config.get("JWT_SECRET_KEY_PATH")) as kf:
                cls.__jwt_secret_key__ = "".join(kf.readlines())
        return cls.__jwt_secret_key__
