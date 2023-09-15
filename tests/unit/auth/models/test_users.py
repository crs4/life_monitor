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

import logging

from lifemonitor.auth import serializers
from lifemonitor.auth.models import User
from lifemonitor.auth.oauth2.client.services import get_current_user_identity
from lifemonitor.auth.services import login_registry, login_user

logger = logging.getLogger()


def test_identity_by_registry_credentials(app_client, user1, client_credentials_registry, user2):

    login_registry(client_credentials_registry)
    user: User = user1['user']
    logger.debug(user)
    logger.debug(user.oauth_identity)

    logger.debug("User1 current identity: %r", user.current_identity)

    assert user.current_identity is not None, "Current identity should not be empty"
    identity = user.current_identity[client_credentials_registry.name]
    assert identity, \
        f"Current identity should contain an identity issued by the provider {client_credentials_registry.name}"
    assert user.current_identity[client_credentials_registry.name].provider == client_credentials_registry.server_credentials, \
        "Unexpected identity provider"

    serialization = serializers.UserSchema().dump(user)
    logger.debug(serialization)
    assert "identities" in serialization, \
        "Unable to find the property 'identity' on the serialized user"
    assert serialization['identities'][client_credentials_registry.name]['provider']['name'] == client_credentials_registry.name, \
        "Invalid provider"

    # check current_identity
    user2_obj = user2['user']
    logger.debug("User2 info: %r", user2)
    assert user2_obj.current_identity is not None, "User2 should not be authenticated"
    assert user2_obj.current_identity[client_credentials_registry.name].provider == client_credentials_registry.server_credentials, \
        "Unexpected identity provider"
    assert user2_obj.current_identity[client_credentials_registry.name].user == user2_obj, \
        "Unexpected identity user"


def test_identity_by_user_credentials(app_client, user1, user2):

    user: User = user1['user']
    logger.debug(user)
    logger.debug(user.oauth_identity)

    # check current_identity before login
    assert user.current_identity is None, "Identity should be empty"

    # login user
    login_user(user)
    logger.debug("User1 current identity: %r", user.current_identity)

    # check current_identity after login
    assert user.current_identity is not None, "Identity should not be empty"

    # check get current user identity
    identity = get_current_user_identity()
    logger.debug("Current user identity: %r", identity)

    user2_obj = user2['user']
    logger.debug(f"User2 Info: {user2}")
    logger.debug(f"User2 Object: {user2_obj}")

    # check oauth identities of user2
    logger.debug(user2_obj.oauth_identity)
    assert user2_obj.oauth_identity is not None, "Identity should not be empty"

    # check current_identity of user2
    logger.debug(f"User2 current identity: {user2_obj.current_identity}")
    assert user2_obj.current_identity is None, "Identity of user2 should be empty"


def test_identity_unavailable(app_client, user1):
    user = user1['user']
    logger.debug(user)
    logger.debug(user.oauth_identity)
    assert user.current_identity is None, "Identity should be empty"
    serialization = serializers.UserSchema().dump(user)
    logger.debug(serialization)
    assert "lifemonitor" in serialization['identities']
    lm_identity = serialization['identities']["lifemonitor"]
    assert lm_identity["provider"]["name"] == "LifeMonitor"
