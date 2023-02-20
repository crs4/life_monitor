# Copyright (c) 2020-2022 CRS4
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

import logging

import connexion
import flask
from flask import current_app, flash, redirect, render_template, request, session, url_for
from flask_login import login_required, login_user, logout_user
from lifemonitor.cache import Timeout, cached, clear_cache
from lifemonitor.utils import (NextRouteRegistry, next_route_aware,
                               split_by_crlf)

from .. import exceptions
from ..utils import OpenApiSpecs, boolean_value
from . import serializers
from .forms import (EmailForm, LoginForm, NotificationsForm, Oauth2ClientForm,
                    RegisterForm, SetPasswordForm)
from .models import db
from .oauth2.client.services import (get_current_user_identity, get_providers,
                                     save_current_user_identity)
from .oauth2.server.services import server
from .services import (authorized, current_registry, current_user,
                       delete_api_key, generate_new_api_key, login_manager)

# Config a module level logger
logger = logging.getLogger(__name__)

blueprint = flask.Blueprint("auth", __name__,
                            url_prefix="/account",
                            template_folder='templates',
                            static_folder="static", static_url_path='../static')

# Set the login view
login_manager.login_view = "auth.login"


def __lifemonitor_service__():
    from lifemonitor.api.services import LifeMonitor
    return LifeMonitor.get_instance()


@authorized
@cached(timeout=Timeout.SESSION)
def show_current_user_profile():
    try:
        if current_user and not current_user.is_anonymous:
            return serializers.UserSchema().dump(current_user)
        raise exceptions.Forbidden(detail="Client type unknown")
    except Exception as e:
        return exceptions.report_problem_from_exception(e)


@authorized
@cached(timeout=Timeout.REQUEST)
def user_notifications_get():
    try:
        if current_user and not current_user.is_anonymous:
            return serializers.ListOfNotifications().dump(current_user.notifications)
        raise exceptions.Forbidden(detail="Client type unknown")
    except Exception as e:
        return exceptions.report_problem_from_exception(e)


@authorized
@cached(timeout=Timeout.REQUEST)
def user_notifications_put(body):
    try:
        if not current_user or current_user.is_anonymous:
            raise exceptions.Forbidden(detail="Client type unknown")
        __lifemonitor_service__().setUserNotificationReadingTime(current_user, body.get('items', []))
        clear_cache()
        return connexion.NoContent, 204
    except Exception as e:
        logger.debug(e)
        return exceptions.report_problem_from_exception(e)


@authorized
@cached(timeout=Timeout.REQUEST)
def user_notifications_patch(body):
    try:
        if not current_user or current_user.is_anonymous:
            raise exceptions.Forbidden(detail="Client type unknown")
        logger.debug("PATCH BODY: %r", body)
        __lifemonitor_service__().deleteUserNotifications(current_user, body)
        clear_cache()
        return connexion.NoContent, 204
    except exceptions.EntityNotFoundException as e:
        return exceptions.report_problem_from_exception(e)
    except Exception as e:
        logger.debug(e)
        return exceptions.report_problem_from_exception(e)


@authorized
@cached(timeout=Timeout.REQUEST)
def user_notifications_delete(notification_uuid):
    try:
        if not current_user or current_user.is_anonymous:
            raise exceptions.Forbidden(detail="Client type unknown")
        __lifemonitor_service__().deleteUserNotification(current_user, notification_uuid)
        clear_cache()
        return connexion.NoContent, 204
    except exceptions.EntityNotFoundException as e:
        return exceptions.report_problem_from_exception(e)
    except Exception as e:
        logger.debug(e)
        return exceptions.report_problem_from_exception(e)


@authorized
def user_subscriptions_get():
    return serializers.ListOfSubscriptions().dump(current_user.subscriptions)


@authorized
@cached(timeout=Timeout.REQUEST)
def get_registry_users():
    try:
        if current_registry and current_user.is_anonymous:
            try:
                return serializers.ListOfUsers().dump(current_registry.users)
            except Exception as e:
                logger.exception(e)
                return {'items': []}
        raise exceptions.Forbidden(detail="Client type unknown")
    except Exception as e:
        return exceptions.report_problem_from_exception(e)


@authorized
@cached(timeout=Timeout.REQUEST)
def get_registry_user(user_id):
    try:
        if current_registry:
            return serializers.UserSchema().dump(current_registry.get_user(user_id))
        raise exceptions.Forbidden(detail="Client type unknown")
    except Exception as e:
        return exceptions.report_problem_from_exception(e)


@blueprint.route("/", methods=("GET",))
def index():
    return redirect(url_for('auth.profile'))


@blueprint.route("/profile", methods=("GET",))
def profile(form=None, passwordForm=None, currentView=None,
            emailForm=None, notificationsForm=None, githubSettingsForm=None, registrySettingsForm=None):
    currentView = currentView or request.args.get("currentView", 'accountsTab')
    logger.debug(OpenApiSpecs.get_instance().authorization_code_scopes)
    back_param = request.args.get('back', None)
    logger.debug("detected back param: %r", back_param)
    if not current_user.is_authenticated:
        session['lm_back_param'] = back_param
        logger.debug("Pushing back param to session")
    else:
        logger.debug("Getting back param from session")
        back_param = back_param or session.get('lm_back_param', False)
        logger.debug("detected back param: %s", back_param)
    from lifemonitor.api.models.registries.forms import RegistrySettingsForm
    from lifemonitor.integrations.github.forms import GithubSettingsForm
    logger.warning("Request args: %r", request.args)
    return render_template("auth/profile.j2",
                           passwordForm=passwordForm or SetPasswordForm(),
                           emailForm=emailForm or EmailForm(),
                           notificationsForm=notificationsForm or NotificationsForm(),
                           enableGithubAppIntegration=boolean_value(current_app.config['ENABLE_GITHUB_INTEGRATION']),
                           enableRegistryIntegration=boolean_value(current_app.config['ENABLE_REGISTRY_INTEGRATION']),
                           oauth2ClientForm=form or Oauth2ClientForm(),
                           githubSettingsForm=githubSettingsForm or GithubSettingsForm.from_model(current_user),
                           registrySettingsForm=registrySettingsForm or RegistrySettingsForm.from_model(current_user),
                           providers=get_providers(), currentView=currentView,
                           oauth2_generic_client_scopes=OpenApiSpecs.get_instance().authorization_code_scopes,
                           back_param=back_param)


@blueprint.route("/register", methods=("GET", "POST"))
def register():
    if flask.request.method == "GET":
        # properly intialize/clear the session before the registration
        flask.session["confirm_user_details"] = True
        flask.session["sign_in"] = False
        save_current_user_identity(None)
    with db.session.no_autoflush:
        form = RegisterForm()
        if form.validate_on_submit():
            user = form.create_user()
            if user:
                login_user(user)
                flash("Account created", category="success")
                clear_cache()
                return redirect(url_for("auth.index"))
        return render_template("auth/register.j2", form=form,
                               action='/register', providers=get_providers())


@blueprint.route("/identity_not_found", methods=("GET", "POST"))
def identity_not_found():
    identity = get_current_user_identity()
    logger.debug("Current provider identity: %r", identity)
    if not identity or not identity.user:
        flash("Unable to register the user")
        return redirect('/login')
    form = RegisterForm()
    user = identity.user
    # workaround to force clean DB session
    from lifemonitor.db import db
    db.session.rollback()
    return render_template("auth/identity_not_found.j2", form=form,
                           action='/register_identity' if flask.session.get('sign_in', False) else '/register',
                           identity=identity, user=user, providers=get_providers())


@blueprint.route("/register_identity", methods=("GET", "POST"))
def register_identity():
    with db.session.no_autoflush:
        identity = get_current_user_identity()
        logger.debug("Current provider identity: %r", identity)
        if not identity:
            flash("Unable to register the user")
            flask.abort(400)
        logger.debug("Provider identity on session: %r", identity)
        logger.debug("User Info: %r", identity.user_info)
        user = identity.user
        form = RegisterForm()
        if form.validate_on_submit():
            user = form.create_user(identity)
            if user:
                login_user(user)
                flash("Account created", category="success")
                clear_cache()
                return redirect(url_for("auth.index"))
        return render_template("auth/register.j2", form=form, action='/register_identity',
                               identity=identity, user=user, providers=get_providers())


@blueprint.route("/login", methods=("GET", "POST"))
@next_route_aware
def login():
    form = LoginForm()
    session.clear()
    flask.session["confirm_user_details"] = True
    flask.session["sign_in"] = True
    if form.validate_on_submit():
        user = form.get_user()
        if user:
            login_user(user)
            session.pop('_flashes', None)
            flash("You have logged in", category="success")
            return redirect(NextRouteRegistry.pop(url_for("auth.index")))
    return render_template("auth/login.j2", form=form, providers=get_providers())


@blueprint.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop('_flashes', None)
    flash("You have logged out", category="success")
    NextRouteRegistry.clear()
    return redirect(url_for("auth.index"))


@blueprint.route("/delete_account", methods=("POST",))
@login_required
def delete_account():
    current_user.delete()
    session.pop('_flashes', None)
    flash("Your account has been deleted", category="success")
    logout_user()
    NextRouteRegistry.clear()
    return redirect(url_for("auth.index"))


@blueprint.route("/set_password", methods=("GET", "POST"))
@login_required
def set_password():
    form = SetPasswordForm()
    if form.validate_on_submit():
        current_user.password = form.password.data
        db.session.add(current_user)
        db.session.commit()
        flash("Password set successfully")
        return redirect(url_for("auth.profile"))
    return profile(passwordForm=form)


@blueprint.route("/set_email", methods=("GET", "POST"))
@login_required
def set_email():
    form = EmailForm()
    if request.method == "GET":
        return profile(emailForm=form, currentView='notificationsTab')
    if form.validate_on_submit():
        if form.email.data == current_user.email:
            flash("email address not changed")
        else:
            current_user.email = form.email.data
            db.session.add(current_user)
            db.session.commit()
            from lifemonitor.mail import send_email_validation_message
            send_email_validation_message(current_user)
            flash("email address registered")
        return redirect(url_for("auth.profile", emailForm=form, currentView='notificationsTab'))
    return profile(emailForm=form, currentView='notificationsTab')


@blueprint.route("/send_verification_email", methods=("GET", "POST"))
@login_required
def send_verification_email():
    try:
        current_user.generate_email_verification_code()
        from lifemonitor.mail import send_email_validation_message
        send_email_validation_message(current_user)
        current_user.save()
        flash("Confirmation email sent")
        logger.info("Confirmation email sent %r", current_user.id)
    except Exception as e:
        logger.error("An error occurred when sending email verification message for user %r",
                     current_user.id)
        logger.debug(e)
    return redirect(url_for("auth.profile", currentView='notificationsTab'))


@blueprint.route("/validate_email", methods=("GET", "POST"))
@login_required
def validate_email():
    validated = False
    try:
        code = request.args.get("code", None)
        current_user.verify_email(code)
        current_user.save()
        flash("Email address validated")
    except exceptions.LifeMonitorException as e:
        logger.debug(e)
    logger.info("Email validated for user %r: %r", current_user.id, validated)
    return redirect(url_for("auth.profile", currentView='notificationsTab'))


@blueprint.route("/update_notifications_switch", methods=("GET", "POST"))
@login_required
def update_notifications_switch():
    logger.debug("Updating notifications")
    form = NotificationsForm()
    if request.method == "GET":
        return redirect(url_for('auth.profile', notificationsForm=form, currentView='notificationsTab'))
    enable_notifications = form.enable_notifications.data
    logger.debug("Enable notifications: %r", enable_notifications)
    if enable_notifications:
        current_user.enable_email_notifications()
    else:
        current_user.disable_email_notifications()
    current_user.save()
    enabled_str = "enabled" if current_user.email_notifications_enabled else "disabled"
    flash(f"email notifications {enabled_str}")
    return redirect(url_for("auth.profile", notificationsForm=form, currentView='notificationsTab'))


@blueprint.route("/update_github_settings", methods=("GET", "POST"))
@login_required
def update_github_settings():
    logger.debug("Updating Github Settings")
    from lifemonitor.integrations.github.forms import GithubSettingsForm
    form = GithubSettingsForm()
    if not form.validate_on_submit():
        return redirect(url_for('auth.profile', githubSettingsForm=form, currentView='githubSettingsTab'))
    form.update_model(current_user)
    current_user.save()
    return redirect(url_for('auth.profile', currentView='githubSettingsTab'))


@blueprint.route("/enable_registry_sync", methods=("GET", "POST",))
@login_required
def enable_registry_sync():
    logger.debug("Enabling Registry Sync")
    if request.method == "GET":
        registry_name = request.values.get("s", None)
        logger.debug("Enabling Registry Sync: %r", registry_name)
        if not registry_name:  # or not current_user.check_secret(registry_name, secret_hash):
            flash("Invalid request: registry cannot be enabled", category="error")
            return redirect(url_for('auth.profile', currentView='registrySettingsTab'))
        else:
            logger.debug("Registry to add: %r", registry_name)
            logger.debug(request.remote_addr)
            from lifemonitor.api.models import WorkflowRegistry
            registry = WorkflowRegistry.find_by_client_name(registry_name)
            if not registry:
                flash("Invalid request: registry not found", category="error")
                return redirect(url_for('auth.profile', currentView='registrySettingsTab'))
            settings = current_user.registry_settings
            settings.add_registry(registry_name)
            registry_user_identity = current_user.oauth_identity[registry.client_name]
            logger.debug("Updated token: %r", registry_user_identity.token)
            assert registry_user_identity, f"No identity found for user of registry {registry.name}"
            assert registry_user_identity.token, f"No token found for user of registry {registry.name}"
            settings.set_token(registry.client_name, registry_user_identity.tokens['read write'])
            current_user.save()
            flash(f"Integration with registry \"{registry.name}\" enabled", category="success")
            return redirect(url_for('auth.profile', currentView='registrySettingsTab'))

    elif request.method == "POST":
        from lifemonitor.api.models.registries.forms import \
            RegistrySettingsForm
        form = RegistrySettingsForm()
        if form.validate_on_submit():
            registry_name = request.values.get("registry", None)
            return redirect(f'/oauth2/login/{registry_name}?scope=read+write&next=/enable_registry_sync?s={registry_name}')
        else:
            logger.debug("Form validation failed")
            flash("Invalid request", category="error")
    # set a fallback redirect
    return redirect(url_for('auth.profile', currentView='registrySettingsTab'))


@blueprint.route("/disable_registry_sync", methods=("POST",))
@login_required
def disable_registry_sync():
    from lifemonitor.api.models.registries.forms import RegistrySettingsForm
    registry_name = request.values.get("registry", None)
    logger.debug("Disabling sync for registry: %r", registry_name)
    form = RegistrySettingsForm()
    settings = current_user.registry_settings
    if form.validate_on_submit():
        from lifemonitor.api.models import WorkflowRegistry
        registry = WorkflowRegistry.find_by_client_name(registry_name)
        if not registry:
            flash("Invalid request: registry not found", category="error")
            return redirect(url_for('auth.profile', currentView='registrySettingsTab'))
        settings.remove_registry(registry_name)
        current_user.save()
        flash(f"Integration with registry \"{registry.name}\" disabled", category="success")
    return redirect(url_for('auth.profile', currentView='registrySettingsTab'))


@blueprint.route("/merge", methods=("GET", "POST"))
@login_required
def merge():
    username = request.args.get("username")
    provider = request.args.get("provider")
    flash(f"Your <b>{provider}</b> identity is already linked to the username "
          f"<b>{username}</b> and cannot be merged to <b>{current_user.username}</b>",
          category="warning")
    return redirect(url_for('auth.profile'))
    # form = LoginForm(data={
    #     "username": username,
    #     "provider": provider})
    # if form.validate_on_submit():
    #     user = form.get_user()
    #     if user:
    #         if user != current_user:
    #             merge_users(current_user, user, request.args.get("provider"))
    #             flash(
    #                 "User {username} has been merged into your account".format(
    #                     username=user.username
    #                 )
    #             )
    #             return redirect(url_for("auth.index"))
    #         else:
    #             form.username.errors.append("Cannot merge with yourself")
    # return render_template("auth/merge.j2", form=form)


@blueprint.route("/create_apikey", methods=("POST",))
@login_required
def create_apikey():
    apikey = generate_new_api_key(
        current_user, " ".join(OpenApiSpecs.get_instance().apikey_scopes.keys()))
    if apikey:
        logger.debug("Created a new API key: %r", apikey)
        flash("API key created!", category="success")
        clear_cache()
    else:
        flash("API key not created!", category="error")
    return redirect(url_for('auth.profile', currentView='apiKeysTab'))


@blueprint.route("/delete_apikey", methods=("POST",))
@login_required
def delete_apikey():
    apikey = request.values.get('apikey', None)
    logger.debug(request.values)
    if not apikey:
        flash("Unable to find the API key")
    else:
        delete_api_key(current_user, apikey)
        clear_cache()
        flash("API key removed!", category="success")
    return redirect(url_for('auth.profile', currentView='apiKeysTab'))


@blueprint.route('/oauth2/clients/save', methods=('POST',))
@login_required
def save_generic_code_flow_client():
    if request.method == "GET":
        return redirect(url_for('auth.profile', currentView='oauth2ClientsTab'))

    form = Oauth2ClientForm(auth_method="client_secret_post")
    if request.method == "POST":
        logger.debug("ClientId: %r", form.clientId.data)
        logger.debug("Name: %r", form.name.data)
        logger.debug("URI: %r", form.uri.data)
        logger.debug("Redirect URI: %r", form.redirect_uris.data)
        logger.debug("Scopes: %r", form.scopes.data)
        logger.debug("Confidential: %r", form.confidential.data)
        logger.debug("AuthMethod: %r", form.auth_method.data)

        for scope in form.scopes:
            logger.debug("A scope: %r", scope.data)
        if form.validate_on_submit():
            data = form.get_client_data()
            if not form.clientId.data:
                client = server.create_client(current_user,
                                              data['name'], data['uri'],
                                              'authorization_code', 'code',
                                              data['scopes'],
                                              split_by_crlf(data["redirect_uris"]),
                                              data['auth_method'])
                logger.debug("lient created: %r", client)
                flash("App Created", category="success")
                clear_cache()
            else:
                clientId = request.values.get('clientId', None)
                client = server.get_client(current_user, clientId)
                if not clientId or not client:
                    flash("Invalid ClientID!", category="error")
                    return profile(form=form, currentView="oauth2ClientsTab")
                server.update_client(current_user, client,
                                     data['name'], data['uri'],
                                     'authorization_code', 'code',
                                     data['scopes'],
                                     split_by_crlf(data["redirect_uris"]),
                                     data['auth_method'])
                logger.debug("Client updated: %r", client)
                flash("App Updated", category="success")
        else:
            logger.debug("Ops... validation failed")
            return profile(form=form, currentView="oauth2ClientEditorPane")
    return redirect(url_for('auth.profile', currentView='oauth2ClientsTab'))


@blueprint.route('/oauth2/clients/edit', methods=('GET', 'POST'))
@login_required
def edit_generic_code_flow_client():
    if request.method == "GET":
        return redirect(url_for('auth.profile', currentView='oauth2ClientsTab'))

    clientId = request.values.get('clientId', None)
    client = server.get_client(current_user, clientId)
    if not clientId or not client:
        flash("Invalid ClientID!", category="error")
        return profile(form=Oauth2ClientForm(), currentView="oauth2ClientsTab")

    form = Oauth2ClientForm.from_object(client)
    logger.debug("Name: %r", form.name.data)
    logger.debug("URI: %r", form.uri.data)
    logger.debug("Redirect URI: %r", form.redirect_uris.data)
    logger.debug("Scopes: %r", form.scopes.data)
    logger.debug("Confidential: %r", form.confidential.data)
    logger.debug("AuthMethod: %r", form.auth_method.data)
    for scope in form.scopes:
        logger.debug("A scope: %r", scope.data)
    clear_cache()
    return profile(form=form, currentView="oauth2ClientEditorPane")


@blueprint.route('/oauth2/clients/delete', methods=('GET', 'POST'))
@login_required
def delete_generic_code_flow_client():
    if request.method == "GET":
        return redirect(url_for('auth.profile', currentView='oauth2ClientsTab'))

    clientId = request.values.get('clientId', None)
    if not clientId:
        flash("Invalid ClientID!", category="error")
    result = server.delete_client(current_user, clientId)
    if not result:
        flash("Unable to delete the OAuth App", category="error")
    else:
        flash("App removed!", category="success")
        clear_cache()
    return redirect(url_for('auth.profile', currentView='oauth2ClientsTab'))
