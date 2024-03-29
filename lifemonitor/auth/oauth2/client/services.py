# Copyright (c) 2020-2024 CRS4
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

import logging

from flask import current_app, session

from lifemonitor import exceptions
from lifemonitor.db import db, db_initialized

from ...models import User
from .models import OAuth2IdentityProvider, OAuth2Registry, OAuthIdentity

# Config a module level logger
logger = logging.getLogger(__name__)

# Create an instance of OAuth registry for oauth clients.
oauth2_registry = OAuth2Registry.get_instance()


def get_providers(skip_registration: bool = False):
    from .providers.github import GitHub
    from .providers.lsaai import LsAAI
    from .providers.seek import Seek
    providers = []
    logger.debug("Preparing list of providers...")
    # set static providers
    if current_app.config.get('GITHUB_CLIENT_ID', None) \
            and current_app.config.get('GITHUB_CLIENT_SECRET', None):
        providers.append(GitHub)
    if current_app.config.get('LSAAI_CLIENT_ID', None) \
            and current_app.config.get('LSAAI_CLIENT_SECRET', None):
        providers.append(LsAAI)
    # set workflow registries as oauth providers
    if db_initialized():
        try:
            logger.debug("Getting dynamic providers...")
            providers.extend(Seek.all())
            logger.debug("Getting providers: %r ... DONE", providers)
        except Exception as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
            logger.warning("Unable to dynamically load oauth providers")
    # The current implementation doesn't support dynamic registration of WorkflowRegistries
    # The following a simple workaround to detect and reconfigure the oauth2registry
    # when the number of workflow registries changes
    if not skip_registration:
        if not oauth2_registry.is_initialized() or (len(oauth2_registry.get_clients()) != len(providers)):
            config_oauth2_registry(current_app, providers=providers)
    logger.debug("Preparing list of providers... DONE")
    return providers


def config_oauth2_registry(app, providers=None):
    logger.debug("Configuring OAuth2 Registry....")
    oauth2_backends = providers or get_providers(skip_registration=True)
    for backend in oauth2_backends:
        oauth2_registry.register_client(backend)
    oauth2_registry.init_app(app)
    logger.debug("OAuth2 registry configured!")


def merge_users(merge_from: User, merge_into: User, provider: str = None):
    assert merge_into != merge_from
    try:
        # start a new transaction
        with db.session.no_autoflush:
            logger.debug("Trying to merge user %r into %r (provider: %r)", merge_from, merge_into, provider)
            # make a copy of the workflow versions submitted by the "merge_from" user
            workflow_versions = list(merge_from.workflow_versions)
            # update the submitter of the workflow versions
            for v in workflow_versions:
                v.submitter = merge_into
                db.session.add(v)
                # update suites submitted by the "merge_from" user
                for s in v.test_suites:
                    if s.submitter == merge_from:
                        s.submitter = merge_into
                        db.session.add(s)
                    # update test instances submitted by the "merge_from" user
                    for i in s.test_instances:
                        if i.submitter == merge_from:
                            i.submitter = merge_into
                            db.session.add(i)

            # update all the remaining permissions
            for permission in list(merge_from.permissions):
                permission.user = merge_into
                db.session.add(permission)

            # move all the authorizations granted to the "merge_from" user to the "merge_into" user
            for auth in list(merge_from.authorizations):
                auth.user = merge_into
                db.session.add(auth)

            # move all the notification of the user "merge_from" to the user "merge_into"
            merge_into_notification_ids = [un.notification.id for un in merge_into.notifications]
            for user_notification in list(merge_from.notifications):
                if user_notification.notification.id not in merge_into_notification_ids:
                    user_notification.user = merge_into
                    db.session.add(user_notification)

            # move all the subscriptions of the user "merge_from" to the user "merge_into"
            for subscription in list(merge_from.subscriptions):
                subscription.user = merge_into
                db.session.add(subscription)

            # move all the api keys of the user "merge_from" to the user "merge_into"
            for api_key in list(merge_from.api_keys):
                api_key.user = merge_into
                db.session.add(api_key)

            # move all the oauth identities of the user "merge_from" to the user "merge_into"
            for identity in list(merge_from.oauth_identity):
                identity.user = merge_into
                db.session.add(identity)

            # move all the clients of the user "merge_from" to the user "merge_into"
            for client in list(merge_from.clients):
                client.user = merge_into
                db.session.add(client)

            # remove the "merge_from" user
            db.session.delete(merge_from)

            # commit the changes
            db.session.add(merge_into)
            db.session.commit()

        # remove the "merge_from" user
        db.session.delete(merge_from)

        # flush the changes
        db.session.flush()
        # remove the "merge_from" user
        return merge_into
    except Exception as e:
        logger.error("Unable to merge users: %r", e)
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        db.session.rollback()
        raise exceptions.LifeMonitorException(title="Unable to merge users") from e


def save_current_user_identity(identity: OAuthIdentity):
    session["oauth2_username"] = identity.user.username \
        if identity and identity.user \
        else identity.user_info["preferred_username"] if identity and identity.user_info else None
    session["oauth2_provider_name"] = identity.provider.client_name if identity else None
    session["oauth2_user_info"] = identity.user_info if identity else None
    session["oauth2_user_token"] = identity.token if identity else None
    logger.debug("User identity temporary save: %r", identity)


def get_current_user_identity():
    try:
        provider_name = session.get("oauth2_provider_name")
        user_info = session.get("oauth2_user_info")
        token = session.get("oauth2_user_token")
        p = OAuth2IdentityProvider.find_by_client_name(provider_name)
        logger.debug("Provider found: %r", p)
        identity = OAuthIdentity(
            provider=p,
            user_info=user_info,
            provider_user_id=user_info["sub"],
            token=token,
        )
        identity.user = User(username=session["oauth2_username"])
        return identity
    except exceptions.EntityNotFoundException as e:
        logger.debug(e)
        return None
