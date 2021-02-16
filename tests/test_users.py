import logging

import pytest
from flask import g

from .conftest import ClientAuthenticationMethod
from .utils import assert_properties_exist

logger = logging.getLogger()


def test_user1(user1):
    assert "user" not in g, "Ops"
    logger.debug("USER 1: %r", user1)
    assert_properties_exist(['user', 'user_info', 'workflows'], user1)
    assert len(user1['workflows']) == 5, "Unexpected number of workflows for user1"
    wfs = [w['name'] for w in user1['workflows']]
    for p in ['basefreqsum', 'sort-and-change-case',
              'sort-and-change-case-invalid-service-url',
              'sort-and-change-case-invalid-service-type']:
        assert p in wfs, f"Expected workflow '{p}'not found"


def test_user2(user2):
    assert "user" not in g, "Ops"
    logger.debug("USER 2: %r", user2)
    assert_properties_exist(['user', 'user_info', 'workflows'], user2)
    assert len(user2['workflows']) == 2, "Unexpected number of workflows for user2"


@pytest.mark.parametrize("client_auth_method", [
    ClientAuthenticationMethod.NOAUTH,
    ClientAuthenticationMethod.BASIC,
    ClientAuthenticationMethod.API_KEY,
    ClientAuthenticationMethod.AUTHORIZATION_CODE,
    ClientAuthenticationMethod.CLIENT_CREDENTIALS,
    ClientAuthenticationMethod.REGISTRY_CODE_FLOW
], indirect=True)
def test_user1_auth(user1, client_auth_method, user1_auth):
    logger.debug("Auth: %r, %r, %r", user1_auth, client_auth_method, ClientAuthenticationMethod.BASIC.value)
    if client_auth_method in [ClientAuthenticationMethod.NOAUTH,
                              ClientAuthenticationMethod.BASIC]:
        assert "ApiKey" not in user1_auth
        assert "Authorization" not in user1_auth
    elif client_auth_method == ClientAuthenticationMethod.API_KEY:
        assert "ApiKey" in user1_auth
    else:
        assert "Bearer" in user1_auth['Authorization']
