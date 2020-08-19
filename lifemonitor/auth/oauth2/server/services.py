from lifemonitor.auth.oauth2.server import Token


def get_token_scopes(access_token):
    """
    The referenced function accepts a token string as argument and
    should return a dict containing a scope field that is either a space-separated list of scopes
    belonging to the supplied token.

    :param access_token:
    :return:
    """
    token = Token.find(access_token)

    return {
        "scope": token.scope if token else []
    }
