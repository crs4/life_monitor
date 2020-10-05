import enum


class TestParam(enum.Enum):

    @classmethod
    def values(cls):
        return [e for e in cls]


class SecurityType(TestParam):
    # BASIC = 'AuthBasic'
    API_KEY = 'ApiKey'
    OAUTH2 = 'Oauth2'


class ClientAuthenticationMethod(TestParam):

    NOAUTH = 'NoAuth',
    BASIC = 'Basic'
    API_KEY = "ApiKey"
    CLIENT_CREDENTIALS = "ClientCredentials"
    AUTHORIZATION_CODE = "AuthorizationCode"


# class ClientSecurityType(TestParam):
class RegistryType(TestParam):
    SEEK = "seek"
