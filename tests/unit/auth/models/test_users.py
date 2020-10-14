import logging
from lifemonitor.auth import serializers
from lifemonitor.auth.services import login_registry


logger = logging.getLogger()


def test_identity(app_client, user1, client_credentials_registry):

    login_registry(client_credentials_registry)
    user = user1['user']
    logger.debug(user)
    logger.debug(user.oauth_identity)

    assert user.current_identity is not None, "Identity should not be empty"
    assert user.current_identity.provider == client_credentials_registry.server_credentials, \
        "Unexpected identity provider"

    serialization = serializers.UserSchema().dump(user)
    logger.debug(serialization)
    assert "identity" in serialization, \
        "Unable to find the property 'identity' on the serialized user"
    assert serialization['identity']['provider']['name'] == client_credentials_registry.name,\
        "Invalid provider"


def test_identity_unavailable(app_client, user1):
    user = user1['user']
    logger.debug(user)
    logger.debug(user.oauth_identity)
    assert user.current_identity is None, "Identity should be empty"
    serialization = serializers.UserSchema().dump(user)
    logger.debug(serialization)
    assert serialization['identity'] == None, \
        "The 'identity' property should be empty on the serialized user"
