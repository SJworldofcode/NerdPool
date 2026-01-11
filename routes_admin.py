# routes_admin.py
import os
import time
from collections import defaultdict
from datetime import datetime, date

from flask import (
    Blueprint, render_template_string, request, redirect,
    url_for, session, abort, flash
)

from db import get_db
from auth import login_required
from template_helpers import get_navbar_context

adminbp = Blueprint("adminbp", __name__)


# --- Utilities ----------------------------------------------------------------
def _day_to_date(val) -> date:
    """Parse various day formats to a date; fallback to today."""
    if isinstance(val, date):
        return val
    s = str(val or "")
    # Prefer ISO yyyy-mm-dd
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        pass
    # Secondary format like: "Aug 24 2025 01:23:45 PM"
    try:
        return datetime.strptime(s.replace(",", ""), "%b %d %Y %I:%M:%S %p").date()
    except Exception:
        pass
    return date.today()

def _has_table(db, name: str) -> bool:
    """Check if a table exists in the database."""
    return db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


# --- Admin guard for this blueprint -------------------------------------------
@adminbp.before_request
def _require_admin():
    # must be logged in
    if not session.get("user_id"):
        return redirect(url_for("authbp.login", next=request.path))
    # must be admin
    try:
        if int(session.get("is_admin", 0)) != 1:
            abort(403)
    except Exception:
        abort(403)


# --- Admin Dashboard -----------------------------------------------------------
@adminbp.route("/admin")
@login_required
def admin_dashboard():
    tmpl = """
    {% extends 'BASE_TMPL' %}{% block content %}
      <h3>Admin Dashboard</h3>
      <div class="grid grid-2">
        <a class="card" href="{{ url_for('adminbp.admin_users') }}" style="text-decoration:none; color:inherit;">
          <h5>Users</h5>
          <div class="muted">Manage users, reset passwords, toggle admin status.</div>
        </a>
        <a class="card" href="{{ url_for('carpoolsbp.admin') }}" style="text-decoration:none; color:inherit;">
          <h5>Pools</h5>
          <div class="muted">Create and manage carpools.</div>
        </a>
        <a class="card" href="{{ url_for('carpoolsbp.memberships') }}" style="text-decoration:none; color:inherit;">
          <h5>Memberships</h5>
          <div class="muted">Manage user memberships in carpools.</div>
        </a>
        <a class="card" href="{{ url_for('adminbp.admin_audit') }}" style="text-decoration:none; color:inherit;">
          <h5>Audit</h5>
          <div class="muted">View audit logs of all changes.</div>
        </a>
        <a class="card" href="{{ url_for('adminbp.admin_diag') }}" style="text-decoration:none; color:inherit;">
          <h5>Diagnostics</h5>
          <div class="muted">View system stats and database info.</div>
        </a>
      </div>
    {% endblock %}
    """
    from templates import BASE_TMPL
    return render_template_string(tmpl, BASE_TMPL=BASE_TMPL, **get_navbar_context())


# --- Users management ----------------------------------------------------------
@adminbp.route("/admin/users", methods=["GET", "POST"])
@login_required
def admin_users():
    """
    Add new users, reset passwords, and toggle admin.
    NOTE: uses raw SHA-256 to match your current DB; you can
    later switch to PBKDF2 in both auth.py and here.
    """
    db = get_db()

    if request.method == "POST":
        action = (request.form.get("action") or "").strip()
        
        if action == "add":
            username = (request.form.get("username") or "").strip()
            if not username:
                flash("Username required.", "error")
                return redirect(url_for("adminbp.admin_users"))
            
            password = (request.form.get("password") or "").strip()
            if not password:
                flash("Password required.", "error")
                return redirect(url_for("adminbp.admin_users"))

            is_admin = 1 if request.form.get("is_admin") else 0
            active = 1 if request.form.get("active") else 0
            
            from hashlib import sha256
            pw_hash = sha256(password.encode()).hexdigest()
            
            try:
                db.execute(
                    "INSERT INTO users(username, password_hash, is_admin, active) VALUES (?,?,?,?)",
                    (username, pw_hash, is_admin, active),
                )
                db.commit()
                flash(f"User '{username}' created.", "info")
            except Exception as e:
                flash(f"Error creating user: {e}", "error")

        elif action == "reset":
            username = (request.form.get("username") or "").strip()
            password = (request.form.get("password") or "").strip()
            is_admin = 1 if request.form.get("is_admin") else 0
            
            if not username or not password:
                flash("Username and Password required for reset.", "error")
                return redirect(url_for("adminbp.admin_users"))

            from hashlib import sha256
            pw_hash = sha256(password.encode()).hexdigest()
            
            db.execute(
                "UPDATE users SET password_hash=?, is_admin=? WHERE username=?",
                (pw_hash, is_admin, username),
            )
            db.commit()
            flash(f"User '{username}' updated.", "info")

        elif action == "toggle_active":
            uid = int(request.form.get("user_id") or 0)
            row = db.execute("SELECT active FROM users WHERE id=?", (uid,)).fetchone()
            if row is not None:
                new_active = 0 if int(row["active"] or 0) == 1 else 1
                db.execute("UPDATE users SET active=? WHERE id=?", (new_active, uid))
                db.commit()
            return redirect(url_for("adminbp.admin_users"))

        elif action == "delete":
            uid = int(request.form.get("user_id") or 0)
            print(f"DEBUG: Attempting to delete user {uid}")
            if uid == session.get("user_id"):
                print("DEBUG: Cannot delete self")
                flash("Cannot delete yourself.", "error")
            else:
                print("DEBUG: Deleting user...")
                db.execute("DELETE FROM user_prefs WHERE user_id=?", (uid,))
                db.execute("DELETE FROM user_carpool_prefs WHERE user_id=?", (uid,))
                db.execute("DELETE FROM carpool_memberships WHERE user_id=?", (uid,))
                db.execute("DELETE FROM entries WHERE user_id=?", (uid,))
                db.execute("DELETE FROM users WHERE id=?", (uid,))
                db.commit()
                flash("User deleted.", "info")
            return redirect(url_for("adminbp.admin_users"))

        else:
            flash("Unknown action.", "error")

        return redirect(url_for("adminbp.admin_users"))

    users = db.execute(
        "SELECT id, username, is_admin, active FROM users ORDER BY username"
    ).fetchall()

    tmpl = """
    {% extends 'BASE_TMPL' %}{% block content %}
      <h3>Users</h3>

      <div class='card'>
        <h5>Add / Update</h5>
        <form method='post' class="row gy-2 align-items-end">
          <input type='hidden' name='action' value='add'>
          <div class="col-auto">
            <label class="form-label">Username
              <input class="form-control" name='username' required>
            </label>
          </div>
          <div class="col-auto">
            <label class="form-label">Password
              <input class="form-control" name='password' type='password' required>
            </label>
          </div>
          <div class="col-auto form-check mt-4">
            <input class="form-check-input" type='checkbox' name='is_admin' id="add_admin">
            <label class="form-check-label" for="add_admin">Admin</label>
          </div>
          <div class="col-auto">
            <button class="btn btn-primary">Save</button>
          </div>
        </form>
      </div>

      <br>

      <div class='card'>
        <h5>Reset Password / Toggle Admin</h5>
        <form method='post' class="row gy-2 align-items-end">
          <input type='hidden' name='action' value='reset'>
          <div class="col-auto">
            <label class="form-label">Username
              <select class="form-select" name='username'>
                {% for u in users %}
                  <option value='{{u["username"]}}'>{{u["username"]}}</option>
                {% endfor %}
              </select>
            </label>
          </div>
          <div class="col-auto">
            <label class="form-label">New Password
              <input class="form-control" name='password' type='password' required>
            </label>
          </div>
          <div class="col-auto form-check mt-4">
            <input class="form-check-input" type='checkbox' name='is_admin' id="reset_admin">
            <label class="form-check-label" for="reset_admin">Admin</label>
          </div>
          <div class="col-auto">
            <button class="btn btn-primary">Update</button>
          </div>
        </form>
      </div>

      <br>

      <table class="table table-sm">
        <thead><tr><th>User</th><th>Admin</th><th>Actions</th></tr></thead>
        <tbody>
          {% for u in users %}
            <tr>
              <td>{{ u['username'] }}</td>
              <td>{{ 'Yes' if u['is_admin'] else 'No' }}</td>
              <td>
                <form method="post" style="display:inline;" onsubmit="return confirm('Delete user {{ u['username'] }}? This cannot be undone.');">
                  <input type="hidden" name="action" value="delete">
                  <input type="hidden" name="user_id" value="{{ u['id'] }}">
                  <button class="btn btn-sm btn-danger" style="padding:2px 6px; font-size:0.8rem;">Del</button>
                </form>
              </td>
            </tr>
          {% endfor %}
          {% if not users %}
            <tr><td colspan="2" class="text-center text-muted">No users</td></tr>
          {% endif %}
        </tbody>
      </table>
    {% endblock %}
    """
    from templates import BASE_TMPL
    return render_template_string(tmpl, users=users, BASE_TMPL=BASE_TMPL, **get_navbar_context())


# --- Audit view ----------------------------------------------------------------
@adminbp.route("/admin/audit", methods=["GET", "POST"])
@login_required
def admin_audit():
    db = get_db()

    # Handle delete action
    if request.method == "POST" and request.form.get("action") == "delete":
        entry_id = int(request.form.get("entry_id") or 0)
        if entry_id:
            db.execute("DELETE FROM entries WHERE id=?", (entry_id,))
            db.commit()
            flash("Entry deleted.", "info")
        return redirect(url_for("adminbp.admin_audit"))

    # Query params
    q = (request.args.get("q") or "").strip()
    member = (request.args.get("member") or "").strip().upper()
    role = (request.args.get("role") or "").strip().upper()
    carpool_filter = (request.args.get("carpool") or "").strip()
    start = (request.args.get("start") or "").strip()  # YYYY-MM-DD
    end   = (request.args.get("end") or "").strip()    # YYYY-MM-DD

    # Get all carpools for filter dropdown
    carpools = db.execute("SELECT id, name FROM carpools ORDER BY name").fetchall() if _has_table(db, "carpools") else []

    rows = db.execute("""
        SELECT e.id, e.day, e.member_key, e.role,
               COALESCE(e.update_user,'') AS update_user,
               COALESCE(e.update_date,'') AS update_date,
               COALESCE(e.update_ts,'')   AS update_ts,
               e.carpool_id,
               c.name AS carpool_name
        FROM entries e
        LEFT JOIN carpools c ON c.id = e.carpool_id
    """).fetchall()

    # Convert + filter in Python (supports non-ISO day formats)
    out = []
    start_d = datetime.strptime(start, "%Y-%m-%d").date() if start else None
    end_d   = datetime.strptime(end,   "%Y-%m-%d").date() if end   else None

    for r in rows:
        d = _day_to_date(r["day"])
        if member and r["member_key"] != member:
            continue
        if role in ("D", "R", "O") and r["role"] != role:
            continue
        if carpool_filter and str(r["carpool_id"]) != carpool_filter:
            continue
        if start_d and d < start_d:
            continue
        if end_d and d > end_d:
            continue
        if q:
            blob = f"{r['day']} {r['member_key']} {r['role']} {r['update_user']} {r['update_date']} {r['update_ts']} {r['carpool_name'] or ''}"
            if q.lower() not in blob.lower():
                continue
        out.append(r)

    # Sort by update_ts (desc), then by day (desc)
    def _sort_key(r):
        uts = str(r["update_ts"] or "")
        try:
            ts = datetime.strptime(uts[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            ts = datetime.min
        return (ts, _day_to_date(r["day"]))
    out.sort(key=_sort_key, reverse=True)

    tmpl = """
    {% extends 'BASE_TMPL' %}{% block content %}
      <h3>Audit History</h3>

      <form class="row g-2 align-items-end mb-3" method="get">
        <div class="col-auto">
          <label class="form-label">Carpool</label>
          <select name="carpool" class="form-select">
            <option value="">(all)</option>
            {% for cp in carpools %}
              <option value="{{ cp['id'] }}" {{ 'selected' if request.args.get('carpool')==cp['id']|string else '' }}>{{ cp['name'] }}</option>
            {% endfor %}
          </select>
        </div>
        <div class="col-auto">
          <label class="form-label">Member</label>
          <select name="member" class="form-select">
            <option value="">(all)</option>
            <option value="CA" {{ 'selected' if request.args.get('member')=='CA' else '' }}>CA</option>
            <option value="ER" {{ 'selected' if request.args.get('member')=='ER' else '' }}>ER</option>
            <option value="SJ" {{ 'selected' if request.args.get('member')=='SJ' else '' }}>SJ</option>
          </select>
        </div>
        <div class="col-auto">
          <label class="form-label">Role</label>
          <select name="role" class="form-select">
            <option value="">(all)</option>
            <option value="D" {{ 'selected' if request.args.get('role')=='D' else '' }}>Driver</option>
            <option value="R" {{ 'selected' if request.args.get('role')=='R' else '' }}>Rider</option>
            <option value="O" {{ 'selected' if request.args.get('role')=='O' else '' }}>Off</option>
          </select>
        </div>
        <div class="col-auto">
          <label class="form-label">From</label>
          <input class="form-control" type="date" name="start" value="{{ request.args.get('start','') }}" pattern="\d{4}-\d{2}-\d{2}">
        </div>
        <div class="col-auto">
          <label class="form-label">To</label>
          <input class="form-control" type="date" name="end" value="{{ request.args.get('end','') }}" pattern="\d{4}-\d{2}-\d{2}">
        </div>
        <div class="col-auto">
          <label class="form-label">Search</label>
          <input class="form-control" name="q" value="{{ request.args.get('q','') }}" placeholder="day/user/date/timestamp">
        </div>
        <div class="col-auto">
          <button class="btn btn-primary">Filter</button>
          <a class="btn btn-secondary" href="{{ url_for('adminbp.admin_audit') }}">Reset</a>
        </div>
      </form>

      <div class="table-scroll">
        <table class="table table-sm table-sticky align-middle">
          <thead>
            <tr>
              <th>Day</th>
              <th>Carpool</th>
              <th>Member</th>
              <th>Role</th>
              <th>Update User</th>
              <th>Update Date</th>
              <th>Timestamp</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {% for r in rows %}
              <tr>
                <td>{{ r['day'] }}</td>
                <td>{{ r['carpool_name'] or '(legacy)' }}</td>
                <td>{{ r['member_key'] }}</td>
                <td>{{ r['role'] }}</td>
                <td>{{ r['update_user'] }}</td>
                <td>{{ r['update_date'] }}</td>
                <td class="muted">{{ r['update_ts'] }}</td>
                <td>
                  <form method="post" style="display:inline;" onsubmit="return confirm('Delete this entry?');">
                    <input type="hidden" name="action" value="delete">
                    <input type="hidden" name="entry_id" value="{{ r['id'] }}">
                    <button class="btn btn-sm btn-danger" style="padding:2px 6px; font-size:0.8rem;">Del</button>
                  </form>
                </td>
              </tr>
            {% endfor %}
            {% if not rows %}
              <tr><td colspan="8" class="text-center text-muted">No audit entries found.</td></tr>
            {% endif %}
          </tbody>
        </table>
      </div>
    {% endblock %}
    """
    from templates import BASE_TMPL
    return render_template_string(tmpl, rows=out, carpools=carpools, BASE_TMPL=BASE_TMPL, **get_navbar_context())


# --- Diagnostics ---------------------------------------------------------------
@adminbp.route("/admin/diag")
@login_required
def admin_diag():
    db = get_db()

    # Find SQLite main path
    main_path = None
    try:
        for _, name, path in db.execute("PRAGMA database_list").fetchall():
            if name == "main":
                main_path = path or ""
                break
    except Exception:
        pass

    exists = os.path.exists(main_path) if main_path else False
    size = os.path.getsize(main_path) if exists else 0
    mtime = os.path.getmtime(main_path) if exists else 0

    rows = db.execute(
        "SELECT day, member_key, role, update_user, update_ts FROM entries"
    ).fetchall()
    n_entries = len(rows)

    # Compute day stats
    by_day = defaultdict(lambda: {"CA": None, "ER": None, "SJ": None})
    day_set = set()
    for r in rows:
        d = r["day"]
        d = _day_to_date(d) if not isinstance(d, date) else d
        day_set.add(d)
        by_day[d][r["member_key"]] = r["role"]

    n_days = len(day_set)
    min_day = f"{min(day_set):%Y-%m-%d}" if day_set else "n/a"
    max_day = f"{max(day_set):%Y-%m-%d}" if day_set else "n/a"

    per_year = []
    year_map = defaultdict(int)
    for d in day_set:
        year_map[d.year] += 1
    for y in sorted(year_map):
        per_year.append({"y": y, "days": year_map[y]})

    newest_days = sorted(day_set, reverse=True)[:25]
    oldest_days = sorted(day_set)[:25]
    newest = [
        {"day": f"{d:%Y-%m-%d}", "CA": by_day[d]["CA"], "ER": by_day[d]["ER"], "SJ": by_day[d]["SJ"]}
        for d in newest_days
    ]
    oldest = [
        {"day": f"{d:%Y-%m-%d}", "CA": by_day[d]["CA"], "ER": by_day[d]["ER"], "SJ": by_day[d]["SJ"]}
        for d in oldest_days
    ]

    def fmt_ts(ts):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else "n/a"

    tmpl = """
    {% extends 'BASE_TMPL' %}{% block content %}
      <h3>Diagnostics</h3>
      <div class="card">
        <div class="row">
          <div class="col-12 col-md-6">
            <table class="table table-sm">
              <tbody>
                <tr><th>SQLite main path</th><td><code>{{ main_path }}</code></td></tr>
                <tr><th>File exists</th><td>{{ 'Yes' if exists else 'No' }}</td></tr>
                <tr><th>Size (bytes)</th><td>{{ size }}</td></tr>
                <tr><th>Modified</th><td>{{ mtime_fmt }}</td></tr>
                <tr><th>Total entries</th><td>{{ n_entries }}</td></tr>
                <tr><th>Distinct days</th><td>{{ n_days }}</td></tr>
                <tr><th>Range</th><td>{{ min_day }} → {{ max_day }}</td></tr>
              </tbody>
            </table>
          </div>
          <div class="col-12 col-md-6">
            <h5>Counts per year</h5>
            <ul class="mb-0">
              {% for r in per_year %}<li>{{ r['y'] }} — {{ r['days'] }}</li>{% endfor %}
            </ul>
          </div>
        </div>
      </div>
      <br>
      <div class="row gy-3">
        <div class="col-12 col-md-6">
          <div class="card">
            <h5>Newest 25 days</h5>
            <pre>{{ newest }}</pre>
          </div>
        </div>
        <div class="col-12 col-md-6">
          <div class="card">
            <h5>Oldest 25 days</h5>
            <pre>{{ oldest }}</pre>
          </div>
        </div>
      </div>
    {% endblock %}
    """
    from templates import BASE_TMPL
    return render_template_string(
        tmpl,
        BASE_TMPL=BASE_TMPL,
        main_path=main_path, exists=exists, size=size,
        mtime_fmt=fmt_ts(mtime), n_entries=n_entries, n_days=n_days,
        min_day=min_day, max_day=max_day, per_year=per_year,
        newest=newest, oldest=oldest,
        **get_navbar_context()
    )
