from __future__ import annotations


class OAuthUserProfile(object):

    def __init__(self, sub=None, name=None, email=None, preferred_username=None,
                 profile=None, picture=None, website=None) -> None:
        self.sub = sub
        self.name = name
        self.email = email
        self.preferred_username = preferred_username
        self.profile = profile
        self.picture = picture
        self.website = website

    def to_dict(self):
        res = {}
        for k in ['sub', 'name', 'email', 'preferred_username', 'profile', 'picture', 'website']:
            res[k] = getattr(self, k)
        return res

    @staticmethod
    def from_dict(data: dict):
        profile = OAuthUserProfile()
        for k, v, in data.items():
            setattr(profile, k, v)
        return profile
