# app_v3.py
from flask import Flask, redirect, url_for
from jinja2 import DictLoader
from datetime import timedelta
from flask_login import current_user

from constants import APP_SECRET, APP_VERSION, DATABASE_URL
from templates import BASE_TMPL, LOGIN_TMPL, TODAY_TMPL, HISTORY_TMPL, STATS_TMPL
from db import get_db, close_db
from auth import authbp, login_manager  # login_manager is defined in auth.py
from routes_today import todaybp
from routes_history import historybp
from routes_admin import adminbp
from routes_account import accountbp
from routes_carpools import carpoolsbp


def create_app():
    app = Flask(__name__)
    app.secret_key = APP_SECRET

    # Make sure db.py uses the same SQLite file everywhere
    app.database_url = DATABASE_URL  # get_db() reads this via current_app.database_url

    # Cookie hardening + remember-me persistence
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        REMEMBER_COOKIE_SECURE=True,
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SAMESITE="Lax",
        REMEMBER_COOKIE_DURATION=timedelta(days=30),
    )

    # Initialize Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = "authbp.login"

    # In-memory templates
    app.jinja_loader = DictLoader({
        "BASE_TMPL": BASE_TMPL,
        "LOGIN_TMPL": LOGIN_TMPL,
        "TODAY_TMPL": TODAY_TMPL,
        "HISTORY_TMPL": HISTORY_TMPL,
        "STATS_TMPL": STATS_TMPL,
    })

    # Optional bridge: keep legacy `{% if is_admin %}` checks working
    @app.context_processor
    def inject_flags():
        return {"is_admin": bool(getattr(current_user, "is_admin", False))}

    # Register blueprints
    app.register_blueprint(accountbp)
    app.register_blueprint(authbp)
    app.register_blueprint(todaybp)
    app.register_blueprint(historybp)
    app.register_blueprint(adminbp)
    app.register_blueprint(carpoolsbp)

    with app.app_context():
        # Run migrations once on startup to avoid per-request races
        _ = get_db()
        close_db(None)

    # Root
    @app.route("/")
    def root():
        return redirect(url_for("todaybp.today"))

    # DB teardown
    @app.teardown_appcontext
    def _close_db(error=None):
        close_db(error)

    return app


if __name__ == "__main__":
    app = create_app()
    print("Carpool v2 modular app starting…")
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=5000)
