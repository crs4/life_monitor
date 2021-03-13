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
    REGISTRY_CODE_FLOW = "RegistryCodeFlow"


# class ClientSecurityType(TestParam):
class RegistryType(TestParam):
    SEEK = "seek"
