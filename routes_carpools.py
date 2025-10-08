# routes_carpools.py
from flask import Blueprint, render_template_string, request, redirect, url_for, session, flash, abort
from auth import login_required
from db import get_db

carpoolsbp = Blueprint("carpoolsbp", __name__, url_prefix="/carpools")

def _is_admin() -> bool:
    try:
        return int(session.get("is_admin", 0)) == 1
    except Exception:
        return False

def _has_table(db, name: str) -> bool:
    return db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None

@carpoolsbp.route("/pick", methods=["GET", "POST"])
@login_required
def pick():
    db = get_db()
    has_multi = _has_table(db, "carpools") and _has_table(db, "carpool_memberships")
    options = []
    if has_multi:
        user_id = session.get("user_id")
        rows = db.execute("""
            SELECT c.id, c.name
            FROM carpool_memberships cm
            JOIN carpools c ON c.id = cm.carpool_id
            WHERE cm.user_id = ? AND cm.active = 1
            ORDER BY c.name
        """, (user_id,)).fetchall()
        options = [{"id": r["id"], "name": r["name"]} for r in rows]
        if request.method == "POST":
            cid = request.form.get("carpool_id")
            row = db.execute("SELECT id, name FROM carpools WHERE id=?", (cid,)).fetchone()
            if row:
                session["carpool_id"] = int(row["id"])
                session["carpool_name"] = row["name"]
                flash(f"Switched to {row['name']}.")
                return redirect(url_for("todaybp.today"))
            flash("NerdPool not found.", "error")
    tmpl = """
    {% extends "BASE_TMPL" %}{% block content %}
      <h3>Switch carpool</h3>
      {% if has_multi %}
        <div class="card">
          {% if options %}
            <form method="post" class="form-row">
              <div style="min-width:260px;">
                <label class="form-label">Pick a carpool</label>
                <select name="carpool_id" class="form-select" required>
                  {% for opt in options %}
                    <option value="{{ opt.id }}" {{ 'selected' if session.get('carpool_id') == opt.id else '' }}>{{ opt.name }}</option>
                  {% endfor %}
                </select>
              </div>
              <div>
                <button class="btn btn-primary" style="margin-top: 26px;">Switch</button>
                <a class="btn btn-secondary" style="margin-top: 26px;" href="{{ url_for('carpoolsbp.clear') }}">Clear</a>
              </div>
            </form>
          {% else %}
            <div class="muted">You don’t belong to any carpools yet.</div>
          {% endif %}
        </div>
      {% else %}
        <div class="card"><div class="muted">Multi-carpool tables aren’t present (legacy mode).</div></div>
      {% endif %}
    {% endblock %}
    """
    from templates import BASE_TMPL
    return render_template_string(tmpl, BASE_TMPL=BASE_TMPL, has_multi=has_multi, options=options)

@carpoolsbp.route("/clear")
@login_required
def clear():
    session.pop("carpool_id", None)
    session.pop("carpool_name", None)
    flash("Cleared carpool selection.")
    return redirect(url_for("todaybp.today"))

@carpoolsbp.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    if not _is_admin(): abort(403)
    db = get_db()
    # Create carpool
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Name required.", "error")
            return redirect(url_for("carpoolsbp.admin"))
        db.execute("CREATE TABLE IF NOT EXISTS carpools (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)")
        db.execute("""
            CREATE TABLE IF NOT EXISTS carpool_memberships (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              carpool_id INTEGER NOT NULL,
              user_id    INTEGER NOT NULL,
              member_key TEXT NOT NULL,
              display_name TEXT NOT NULL,
              active INTEGER NOT NULL DEFAULT 1,
              UNIQUE(carpool_id, member_key),
              UNIQUE(carpool_id, user_id),
              FOREIGN KEY(carpool_id) REFERENCES carpools(id) ON DELETE CASCADE,
              FOREIGN KEY(user_id)    REFERENCES users(id)    ON DELETE CASCADE
            )
        """)
        db.execute("INSERT OR IGNORE INTO carpools(name) VALUES (?)", (name,))
        db.commit()
        flash(f"Carpool '{name}' created.", "info")
        return redirect(url_for("carpoolsbp.admin"))

    rows = db.execute("SELECT id, name FROM carpools ORDER BY name").fetchall() if _has_table(db,"carpools") else []
    tmpl = """
    {% extends "BASE_TMPL" %}{% block content %}
      <h3>NerdPools</h3>
      <form method="post" class="card mb-3">
        <div class="row gy-2 align-items-end">
          <div class="col-auto">
            <label class="form-label">Name
              <input class="form-control" name="name" placeholder="Team A" required>
            </label>
          </div>
          <div class="col-auto">
            <button class="btn btn-primary">Add</button>
            <a class="btn btn-secondary" href="{{ url_for('carpoolsbp.memberships') }}">Memberships</a>
          </div>
        </div>
      </form>
      <table class="table table-sm"><thead><tr><th>ID</th><th>Name</th></tr></thead>
      <tbody>{% for r in rows %}<tr><td>{{ r['id'] }}</td><td>{{ r['name'] }}</td></tr>{% endfor %}</tbody></table>
    {% endblock %}
    """
    from templates import BASE_TMPL
    return render_template_string(tmpl, BASE_TMPL=BASE_TMPL, rows=rows)

@carpoolsbp.route("/memberships", methods=["GET","POST"])
@login_required
def memberships():
    if not _is_admin(): abort(403)
    db = get_db()

    # Ensure tables
    db.execute("CREATE TABLE IF NOT EXISTS carpools (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)")
    db.execute("""
        CREATE TABLE IF NOT EXISTS carpool_memberships (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          carpool_id INTEGER NOT NULL,
          user_id    INTEGER NOT NULL,
          member_key TEXT NOT NULL,
          display_name TEXT NOT NULL,
          active INTEGER NOT NULL DEFAULT 1,
          UNIQUE(carpool_id, member_key),
          UNIQUE(carpool_id, user_id),
          FOREIGN KEY(carpool_id) REFERENCES carpools(id) ON DELETE CASCADE,
          FOREIGN KEY(user_id)    REFERENCES users(id)    ON DELETE CASCADE
        )
    """)

    if request.method == "POST":
        carpool_id = int(request.form.get("carpool_id") or 0)
        username = (request.form.get("username") or "").strip()
        member_key = (request.form.get("member_key") or "").strip().upper()
        display_name = (request.form.get("display_name") or "").strip()
        active = 1 if request.form.get("active") else 0

        if not (carpool_id and username and member_key and display_name):
            flash("All fields required.", "error")
            return redirect(url_for("carpoolsbp.memberships"))

        u = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if not u:
            flash("User not found. Create user under Admin > Users.", "error")
            return redirect(url_for("carpoolsbp.memberships"))

        db.execute("""
            INSERT OR REPLACE INTO carpool_memberships(carpool_id, user_id, member_key, display_name, active)
            VALUES (?,?,?,?,?)
        """, (carpool_id, u["id"], member_key, display_name, active))
        db.commit()
        flash("Membership saved.", "info")
        return redirect(url_for("carpoolsbp.memberships"))

    carpools = db.execute("SELECT id, name FROM carpools ORDER BY name").fetchall()
    users = db.execute("SELECT id, username FROM users ORDER BY username").fetchall()
    memberships = db.execute("""
        SELECT cm.id, c.name AS carpool, u.username, cm.member_key, cm.display_name, cm.active
        FROM carpool_memberships cm
        JOIN carpools c ON c.id=cm.carpool_id
        JOIN users u ON u.id=cm.user_id
        ORDER BY c.name, u.username
    """).fetchall()

    tmpl = """
    {% extends "BASE_TMPL" %}{% block content %}
      <h3>Memberships</h3>
      <form method="post" class="card mb-3">
        <div class="row gy-2 align-items-end">
          <div class="col-auto">
            <label class="form-label">Carpool
              <select class="form-select" name="carpool_id">
                {% for c in carpools %}<option value="{{c['id']}}">{{c['name']}}</option>{% endfor %}
              </select>
            </label>
          </div>
          <div class="col-auto">
            <label class="form-label">Username
              <input class="form-control" name="username" placeholder="Christian">
            </label>
          </div>
          <div class="col-auto">
            <label class="form-label">Member Key
              <input class="form-control" name="member_key" placeholder="CA" maxlength="4">
            </label>
          </div>
          <div class="col-auto">
            <label class="form-label">Display Name
              <input class="form-control" name="display_name" placeholder="Christian">
            </label>
          </div>
          <div class="col-auto form-check mt-4">
            <input class="form-check-input" type="checkbox" name="active" id="active">
            <label class="form-check-label" for="active">Active</label>
          </div>
          <div class="col-auto">
            <button class="btn btn-primary">Save</button>
          </div>
        </div>
      </form>

      <table class="table table-sm">
        <thead><tr><th>Carpool</th><th>User</th><th>Key</th><th>Name</th><th>Active</th></tr></thead>
        <tbody>
        {% for m in memberships %}
          <tr><td>{{m['carpool']}}</td><td>{{m['username']}}</td><td>{{m['member_key']}}</td><td>{{m['display_name']}}</td><td>{{'Yes' if m['active'] else 'No'}}</td></tr>
        {% endfor %}
        </tbody>
      </table>
    {% endblock %}
    """
    from templates import BASE_TMPL
    return render_template_string(tmpl, BASE_TMPL=BASE_TMPL, carpools=carpools, users=users, memberships=memberships)
