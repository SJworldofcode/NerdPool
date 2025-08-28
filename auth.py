# auth.py
from flask import Blueprint, request, redirect, url_for, render_template_string, flash, session
from hashlib import sha256
from templates import LOGIN_TMPL
from db import get_db

# Flask-Login
from flask_login import (
    UserMixin, login_user, logout_user,
    login_required as _fl_login_required, current_user, LoginManager
)

authbp = Blueprint("authbp", __name__)

# Create the LoginManager here; app_v2.py will init it
login_manager = LoginManager()
login_required = _fl_login_required  # re-export so existing imports keep working


# ---- User model & loader ----
class User(UserMixin):
    def __init__(self, id, username, is_admin=False):
        self.id = str(id)  # Flask-Login expects a str-ish id
        self.username = username
        # normalize 0/1 or "0"/"1" to a real boolean
        self.is_admin = (int(is_admin) == 1)

@login_manager.user_loader
def load_user(user_id: str):
    db = get_db()
    row = db.execute(
        "SELECT id, username, is_admin FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    if not row:
        return None
    return User(row["id"], row["username"], row["is_admin"])


# ---- Routes ----
@authbp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        remember = bool(request.form.get("remember"))

        db = get_db()
        row = db.execute(
            "SELECT id, username, password_hash, is_admin FROM users WHERE username=?",
            (username,)
        ).fetchone()

        # Legacy SHA-256 check (matches your current DB contents)
        if row and row["password_hash"] == sha256(password.encode()).hexdigest():
            user = User(row["id"], row["username"], row["is_admin"])
            login_user(user, remember=remember)

            # Bridge for blueprints still using session (routes_admin.before_request)
            session["user_id"] = int(user.id)
            session["username"] = user.username
            session["is_admin"] = 1 if user.is_admin else 0

            return redirect(request.args.get("next") or url_for("todaybp.today"))

        flash("Invalid credentials", "error")

    return render_template_string(LOGIN_TMPL)


@authbp.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()  # clear legacy keys too
    return redirect(url_for("authbp.login"))


@authbp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    from templates import BASE_TMPL  # avoid circular with DictLoader in app factory
    if request.method == "POST":
        pw1 = request.form.get("pw1", "")
        pw2 = request.form.get("pw2", "")
        if not pw1 or pw1 != pw2:
            flash("Passwords do not match", "error")
        else:
            db = get_db()
            db.execute(
                "UPDATE users SET password_hash=? WHERE id=?",
                (sha256(pw1.encode()).hexdigest(), current_user.id)
            )
            db.commit()
            flash("Password updated.")
            return redirect(url_for("authbp.account"))

    tmpl = """
    {% extends 'BASE_TMPL' %}{% block content %}
      <h3>Account</h3>
      <form method='post' class='card'>
        <label>New password<br><input type='password' name='pw1' required></label><br><br>
        <label>Confirm password<br><input type='password' name='pw2' required></label><br><br>
        <label><input type="checkbox" name="remember"> Keep me signed in on this device</label><br><br>
        <button class="btn btn-primary">Change password</button>
      </form>
    {% endblock %}
    """
    return render_template_string(tmpl, BASE_TMPL=BASE_TMPL)
