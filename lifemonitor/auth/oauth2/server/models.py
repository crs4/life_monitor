from __future__ import annotations
import time
from typing import List
from authlib.integrations.flask_oauth2 import AuthorizationServer as OAuth2AuthorizationServer
from authlib.oauth2.rfc6749 import grants, InvalidRequestError
from authlib.common.security import generate_token
from authlib.integrations.sqla_oauth2 import (
    OAuth2AuthorizationCodeMixin,
    OAuth2ClientMixin,
    OAuth2TokenMixin,
    create_query_client_func,
    create_save_token_func
)
from lifemonitor.db import db
from werkzeug.security import gen_salt
from lifemonitor.auth.models import User
from datetime import datetime


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

    @property
    def redirect_uris(self):
        return self.client_metadata.get('redirect_uris', [])

    @redirect_uris.setter
    def redirect_uris(self, value):
        if isinstance(value, str):
            value = value.split(',')
        metadata = self.client_metadata
        metadata['redirect_uris'] = value
        self.set_client_metadata(metadata)

    @classmethod
    def find_by_id(cls, client_id) -> Client:
        return cls.query.get(client_id)

    @classmethod
    def all(cls) -> List[Client]:
        return cls.query.all()


class Token(db.Model, OAuth2TokenMixin):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey('user.id', ondelete='CASCADE')
    )
    user = db.relationship('User')
    client_id = db.Column(db.String,
                          db.ForeignKey('client.client_id', ondelete='CASCADE'))
    client = db.relationship('Client')

    def is_expired(self) -> bool:
        return datetime.utcnow().timestamp() - self.get_expires_at() > 0

    def is_refresh_token_valid(self) -> bool:
        return self if not self.revoked else None

    def save(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @classmethod
    def find(cls, access_token):
        return cls.query.filter(Token.access_token == access_token).first()

    @classmethod
    def find_by_user(cls, user: User) -> List[Token]:
        return cls.query.filter(Token.user == user).all()

    @classmethod
    def all(cls):
        return cls.query.all()


class AuthorizationServer(OAuth2AuthorizationServer):

    def __init__(self, app=None):
        super().__init__(app,
                         query_client=create_query_client_func(db.session, Client),
                         save_token=create_save_token_func(db.session, Token))
        # register it to grant endpoint
        self.register_grant(AuthorizationCodeGrant)
        # register it to grant endpoint
        self.register_grant(grants.ImplicitGrant)
        # register it to grant endpoint
        self.register_grant(PasswordGrant)
        # register it to grant endpoint
        self.register_grant(ClientCredentialsGrant)
        # register it to grant endpoint
        self.register_grant(RefreshTokenGrant)

    @staticmethod
    def create_client(user,
                      client_name, client_uri,
                      grant_type, response_type, scope,
                      redirect_uri,
                      token_endpoint_auth_method=None, commit=True):
        client_id = gen_salt(24)
        client_id_issued_at = int(time.time())
        client = Client(
            client_id=client_id,
            client_id_issued_at=client_id_issued_at,
            user_id=user.id,
        )

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
        else:
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


class AuthorizationCode(db.Model, OAuth2AuthorizationCodeMixin):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey('user.id', ondelete='CASCADE')
    )
    user = db.relationship('User')


class AuthorizationCodeGrant(grants.AuthorizationCodeGrant):
    TOKEN_ENDPOINT_AUTH_METHODS = [
        'client_secret_basic', 'client_secret_post'
    ]

    def create_authorization_code(self, client, grant_user, request):
        # you can use other method to generate this code
        code = generate_token(48)
        item = AuthorizationCode(
            code=code,
            client_id=client.client_id,
            redirect_uri=request.redirect_uri,
            scope=request.scope,
            user_id=grant_user.get_user_id(),
        )
        db.session.add(item)
        db.session.commit()
        return code

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
