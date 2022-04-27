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

from typing import List

from lifemonitor.auth.models import User
from lifemonitor.integrations.github.utils import match_ref
from sqlalchemy.orm.attributes import flag_modified


class GithubUserSettings():

    DEFAULTS = {
        "check_issues": True,
        "public": True,
        "all_branches": True,
        "all_tags": True,
        "branches": ["main"],
        "tags": ["v*.*.*"]
    }

    def __init__(self, user: User) -> None:
        self.user = user
        self._raw_settings = self.user.settings.get('github_settings', None)
        if not self._raw_settings:
            self._raw_settings = self.DEFAULTS.copy()
            self.user.settings['github_settings'] = self._raw_settings

    @property
    def public(self) -> bool:
        return self._raw_settings.get('public', self.DEFAULTS['public'])

    @property
    def check_issues(self) -> bool:
        return self._raw_settings.get('check_issues', self.DEFAULTS['check_issues'])

    @check_issues.setter
    def check_issues(self, value: bool):
        self._raw_settings['check_issues'] = value
        flag_modified(self.user, 'settings')

    @property
    def all_branches(self) -> bool:
        return self._raw_settings.get('all_branches', self.DEFAULTS['all_branches'])

    @all_branches.setter
    def all_branches(self, value: bool):
        self._raw_settings['all_branches'] = value
        flag_modified(self.user, 'settings')

    @property
    def all_tags(self) -> bool:
        return self._raw_settings.get('all_tags', self.DEFAULTS['all_tags'])

    @all_tags.setter
    def all_tags(self, value: bool):
        self._raw_settings['all_tags'] = value
        flag_modified(self.user, 'settings')

    @property
    def branches(self) -> List[str]:
        return self._raw_settings.get('branches', self.DEFAULTS['branches']).copy()

    @branches.setter
    def branches(self, branches: List[str]) -> List[str]:
        self._raw_settings['branches'] = branches.copy()
        flag_modified(self.user, 'settings')

    def add_branch(self, branch: str):
        self._raw_settings['branches'].append(branch)
        flag_modified(self.user, 'settings')

    def remove_branch(self, branch: str):
        self._raw_settings['branches'].remove(branch)
        flag_modified(self.user, 'settings')

    def is_valid_branch(self, branch: str) -> bool:
        return match_ref(branch, self.branches)

    @property
    def tags(self) -> List[str]:
        return self._raw_settings.get('tags', self.DEFAULTS['tags']).copy()

    @tags.setter
    def tags(self, tags: List[str]) -> List[str]:
        self._raw_settings['tags'] = tags.copy()
        flag_modified(self.user, 'settings')

    def add_tag(self, tag: str):
        self._raw_settings['tags'].append(tag)
        flag_modified(self.user, 'settings')

    def remove_tag(self, tag: str):
        self._raw_settings['tags'].remove(tag)
        flag_modified(self.user, 'settings')

    def is_valid_tag(self, tag: str) -> bool:
        return match_ref(tag, self.tags)


def __get_github_settings(self) -> GithubUserSettings:
    prop_name = '_github_settings'
    settings = getattr(self, prop_name, None)
    if not settings:
        settings = GithubUserSettings(self)
        setattr(self, prop_name, settings)
    return settings


User.github_settings = property(__get_github_settings)
