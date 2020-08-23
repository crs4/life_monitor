import logging

import flask
from flask_login import login_required, login_user, logout_user, current_user

from .forms import RegisterForm, LoginForm, SetPasswordForm
from .models import db, User
from .oauth2.client import oauth2_registry
from .oauth2.client.services import merge_users
from .services import login_manager

# Config a module level logger
logger = logging.getLogger(__name__)

blueprint = Blueprint("auth", __name__,
                      template_folder='templates',
                      static_folder="static", static_url_path='/static/auth')

# Set the login view
login_manager.login_view = "auth.login"

@blueprint.route("/", methods=("GET",))
def index():
    return render_template("auth/profile.j2")


@blueprint.route("/profile", methods=("GET",))
def profile():
    return render_template("auth/profile.j2")


@blueprint.route("/register", methods=("GET", "POST"))
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = form.create_user()
        if user:
            login_user(user)
            flash("Account created")
            return redirect(url_for("auth.index"))
    return render_template("auth/register.j2", form=form)


@blueprint.route("/login/", methods=("GET", "POST"))
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = form.get_user()
        if user:
            login_user(user)
            flash("You have logged in")
            return redirect(url_for("auth.index"))
    return render_template("auth/login.j2", form=form)


@blueprint.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have logged out")
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
        return redirect(url_for("auth.index"))
    return render_template("auth/set_password.j2", form=form)


@blueprint.route("/merge", methods=("GET", "POST"))
@login_required
def merge():
    form = LoginForm(data={
        "username": request.args.get("username"),
        "provider": request.args.get("provider")})
    if form.validate_on_submit():
        user = form.get_user()
        if user:
            if user != current_user:
                merge_users(current_user, user, request.args.get("provider"))
                flash(
                    "User {username} has been merged into your account".format(
                        username=user.username
                    )
                )
                return redirect(url_for("auth.index"))
            else:
                form.username.errors.append("Cannot merge with yourself")
    return render_template("auth/merge.j2", form=form)
