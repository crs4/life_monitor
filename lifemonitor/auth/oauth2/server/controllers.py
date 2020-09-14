from flask import request, render_template, redirect, Blueprint, jsonify
from flask_login import current_user, login_required

from .services import server
from .utils import split_by_crlf

blueprint = Blueprint("oauth2_server", __name__,
                      template_folder='templates',
                      static_folder="static", static_url_path='/static/auth2')


@blueprint.route('/oauth/authorize', methods=['GET', 'POST'])
@login_required
def authorize():
    # Login is required since we need to know the current resource owner.
    # It can be done with a redirection to the login page, or a login
    # form on this authorization page.
    if request.method == 'GET':
        grant = server.validate_consent_request(end_user=current_user)
        return render_template(
            'authorize.html',
            grant=grant,
            user=current_user,
        )
    confirmed = request.form['confirm']
    if confirmed:
        # granted by resource owner
        return server.create_authorization_response(grant_user=current_user)
    # denied by resource owner
    return server.create_authorization_response(grant_user=None)


@blueprint.route('/oauth/token', methods=['POST'])
def issue_token():
    return server.create_token_response()


@blueprint.route('/oauth/create_client', methods=('GET', 'POST'))
@login_required
def create_client():
    user = current_user
    if not user:
        return redirect('/login')
    if request.method == 'GET':
        return render_template('create_client.html')

    form = request.form
    client = server.create_client(user,
                                  form["client_name"], form["client_uri"],
                                  split_by_crlf(form["grant_type"]),
                                  split_by_crlf(form["response_type"]),
                                  form["scope"],
                                  split_by_crlf(form["redirect_uri"]),
                                  form["token_endpoint_auth_method"]
                                  )
    return jsonify({
        "client_id": client.client_id,
        "client_secret": client.client_secret
    })
