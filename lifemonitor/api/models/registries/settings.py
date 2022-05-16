# Copyright (c) 2020-2021 CRS4
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

from __future__ import annotations

from typing import Dict, List

from lifemonitor.auth import User
from sqlalchemy.orm.attributes import flag_modified

from lifemonitor.auth.oauth2.client.models import OAuth2Token


class RegistrySettings():

    def __init__(self, user: User) -> None:
        self.user = user
        self._raw_settings = self.user.settings.get('registry_settings', None)
        if not self._raw_settings:
            self._raw_settings = {}
            self.user.settings['registry_settings'] = self._raw_settings

    def get_token(self, registry: str) -> OAuth2Token:
        token = self._raw_settings[registry].get('token', None) if registry in self._raw_settings else None
        return OAuth2Token(token) if token else None

    def set_token(self, registry: str, token: Dict):
        if registry not in self._raw_settings:
            raise ValueError(f"Registry {registry} not found")
        self._raw_settings[registry]['token'] = token
        flag_modified(self.user, 'settings')

    @property
    def registries(self) -> List[str]:
        return self._raw_settings.keys()

    @registries.setter
    def registries(self, registries: List[str]) -> List[str]:
        self._raw_settings = {r: {} for r in registries}
        flag_modified(self.user, 'settings')

    def add_registry(self, registry: str):
        if registry not in self.registries:
            self._raw_settings[registry] = {}
            flag_modified(self.user, 'settings')

    def remove_registry(self, registry: str):
        if registry in self.registries:
            del self._raw_settings[registry]
            flag_modified(self.user, 'settings')

    def is_registry_enabled(self, registry: str) -> bool:
        return registry in self.registries


def __get_registry_settings(self) -> RegistrySettings:
    prop_name = '_registry_settings'
    settings = getattr(self, prop_name, None)
    if not settings:
        settings = RegistrySettings(self)
        setattr(self, prop_name, settings)
    return settings


User.registry_settings = property(__get_registry_settings)
