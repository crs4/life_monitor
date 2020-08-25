from __future__ import annotations
import time

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
from werkzeug.security import gen_salt

from lifemonitor.app import db
from lifemonitor.auth.models import User


class Client(db.Model, OAuth2ClientMixin):
    id = db.Column(db.Integer, primary_key=True)
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


class Token(db.Model, OAuth2TokenMixin):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey('user.id', ondelete='CASCADE')
    )
    user = db.relationship('User')

    def save(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @classmethod
    def find(cls, access_token):
        return cls.query.filter(Token.access_token == access_token).first()


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
                      token_endpoint_auth_method=None):
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

        db.session.add(client)
        db.session.commit()
        return client


class AuthorizationCode(db.Model, OAuth2AuthorizationCodeMixin):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey('user.id', ondelete='CASCADE')
    )
    user = db.relationship('User')


class AuthorizationCodeGrant(grants.AuthorizationCodeGrant):

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
            raise InvalidRequestError("Username %s not found".format(username))
        if not user.check_password(password):
            return InvalidRequestError("Password not valid!")
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
        if item and item.is_refresh_token_valid():
            return item

    def authenticate_user(self, credential):
        return User.query.get(credential.user_id)

    def revoke_old_credential(self, credential):
        credential.revoked = True
        db.session.add(credential)
        db.session.commit()
