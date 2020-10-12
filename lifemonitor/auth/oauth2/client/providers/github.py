import logging

# Config a module level logger
logger = logging.getLogger(__name__)


def normalize_userinfo(client, data):
    logger.debug(data)
    params = {
        'sub': str(data['id']),
        'name': data['name'],
        'email': data.get('email'),
        'preferred_username': data['login'],
        'profile': data['html_url'],
        'picture': data['avatar_url'],
        'website': data.get('blog'),
    }

    # The email can be be None despite the scope being 'user:email'.
    # That is because a user can choose to make his/her email private.
    # If that is the case we get all the users emails regardless if private or note
    # and use the one he/she has marked as `primary`
    if params.get('email') is None:
        resp = client.get('user/emails')
        resp.raise_for_status()
        data = resp.json()
        params["email"] = next(email['email'] for email in data if email['primary'])
    return params


class GitHub:
    name = 'github'
    oauth_config = {
        'api_base_url': 'https://api.github.com/',
        'access_token_url': 'https://github.com/login/oauth/access_token',
        'authorize_url': 'https://github.com/login/oauth/authorize',
        'client_kwargs': {'scope': 'user:email'},
        'userinfo_endpoint': 'https://api.github.com/user',
        'userinfo_compliance_fix': normalize_userinfo,
    }

    @staticmethod
    def normalize_userinfo(client, data):
        return normalize_userinfo(client, data)
