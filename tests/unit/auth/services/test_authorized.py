import pytest
import logging
from tests import utils
from lifemonitor.lang import messages
from lifemonitor.auth import models
from lifemonitor.auth import services
from werkzeug.wrappers import Response
from tests import conftest_helpers as helpers

logger = logging.getLogger()


@pytest.fixture
def authorized_func(mocker):
    f = mocker.Mock(name="AuthorizedFunction")
    return services.authorized(f)


def test_unauthorized_no_user_nor_registry(app_client, authorized_func):

    with pytest.raises(services.NotAuthorizedException) as e:
        authorized_func()
    utils.assert_error_message(messages.unauthorized_no_user_nor_registry, e)


def test_unauthorized_user_without_identity(app_client,
                                            client_credentials_registry, authorized_func):
    user = models.User()
    services.login_user(user)
    registry = client_credentials_registry
    services.login_registry(registry)

    with pytest.raises(services.NotAuthorizedException) as e:
        authorized_func()
    utils.assert_error_message(
        messages.unauthorized_user_without_registry_identity.format(registry.name), e)


def test_unauthorized_user_with_expired_registry_token(app_client, user1, authorized_func,
                                                       client_credentials_registry):
    helpers.enable_auto_login(user1['user'])
    user = user1['user']
    logger.debug(f"The user: {user}")
    services.login_user(user)
    registry = client_credentials_registry
    services.login_registry(registry)
    assert registry.name in user.oauth_identity, "Missing user identity"
    identity = user.oauth_identity[registry.name]
    # extract the identity token
    token = identity.token
    # ensure the token doesn't have a refresh token
    token.pop('refresh_token', False)
    # make the token expired
    token['expires_at'] = token['created_at']
    user_info = identity.user_info
    logger.debug(user_info)
    # calling the decorator with such a token
    # will result in a redirection
    response = authorized_func()
    logger.debug(response)
    assert isinstance(response, Response)
    assert response.status_code == 307, "Unexpected status code"
    # the redirection to the original endpoint is marked with param 'redirection'
    # and if the token is still expired an error will be reported
    with app_client.application.test_request_context('/?redirection=true'):
        services.login_user(user)
        services.login_registry(registry)
        with pytest.raises(services.NotAuthorizedException) as e:
            authorized_func()
        utils.assert_error_message(
            messages.unauthorized_user_with_expired_registry_token.format(
                registry.name, registry.name), e)
