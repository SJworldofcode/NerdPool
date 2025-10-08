# routes_account.py
from flask import Blueprint, render_template_string, session, request, redirect, url_for, flash
from datetime import date, datetime
from hashlib import sha256
from collections import defaultdict

from db import get_db
from auth import login_required
from templates import BASE_TMPL

accountbp = Blueprint("accountbp", __name__)

def _day_to_date(val):
    if isinstance(val, date): return val
    s = str(val or "")
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        pass
    try:
        return datetime.strptime(s.replace(",", ""), "%b %d %Y %I:%M:%S %p").date()
    except Exception:
        pass
    return date.today()

def _has_table(db, name: str) -> bool:
    return db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None

def _has_column(db, table: str, col: str) -> bool:
    cols = {r["name"] for r in db.execute(f"PRAGMA table_info({table})").fetchall()}
    return col in cols

def _is_multi_mode(db) -> bool:
    return (
        _has_table(db, "carpools")
        and _has_table(db, "carpool_memberships")
        and _has_column(db, "entries", "carpool_id")
        and _has_column(db, "entries", "user_id")
    )

def _get_global_prefs(db, user_id):
    row = db.execute("SELECT gas_price, avg_mpg, miles_per_ride FROM user_prefs WHERE user_id=?", (user_id,)).fetchone()
    if not row:
        return 4.78, 22.0, 36.0
    return float(row["gas_price"]), float(row["avg_mpg"]), float(row["miles_per_ride"])

def _get_carpool_mprs(db, user_id):
    """
    Returns list of {id, name, mpr} for user's active memberships.
    If the multicarpool tables don't exist, returns [].
    """
    if not _is_multi_mode(db):
        return []
    rows = db.execute("""
        SELECT c.id, c.name,
               COALESCE(ucp.miles_per_ride, 36.0) AS mpr
        FROM carpool_memberships cm
        JOIN carpools c ON c.id = cm.carpool_id
        LEFT JOIN user_carpool_prefs ucp
               ON ucp.user_id = cm.user_id AND ucp.carpool_id = cm.carpool_id
        WHERE cm.user_id=? AND cm.active=1
        ORDER BY c.name
    """, (user_id,)).fetchall()
    return [{"id": r["id"], "name": r["name"], "mpr": float(r["mpr"])} for r in rows]

def _save_global_prefs(db, user_id, gas_price, avg_mpg, legacy_mpr=None):
    # Keep miles_per_ride only for legacy mode
    if legacy_mpr is None:
        db.execute("""
            INSERT INTO user_prefs(user_id, gas_price, avg_mpg)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
              gas_price=excluded.gas_price,
              avg_mpg=excluded.avg_mpg
        """, (user_id, gas_price, avg_mpg))
    else:
        db.execute("""
            INSERT INTO user_prefs(user_id, gas_price, avg_mpg, miles_per_ride)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
              gas_price=excluded.gas_price,
              avg_mpg=excluded.avg_mpg,
              miles_per_ride=excluded.miles_per_ride
        """, (user_id, gas_price, avg_mpg, legacy_mpr))
    db.commit()

def _save_mprs(db, user_id, mpr_map):
    # mpr_map: { carpool_id -> miles_per_ride }
    for cid, mpr in mpr_map.items():
        db.execute("""
            INSERT INTO user_carpool_prefs(user_id, carpool_id, miles_per_ride)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, carpool_id) DO UPDATE SET
              miles_per_ride=excluded.miles_per_ride
        """, (user_id, cid, mpr))
    db.commit()

def _count_rides_by_carpool(db, user_id):
    """
    Count rides for this user per carpool (only days <= today AND with a driver).
    Returns dict {carpool_id or 'legacy': rides_count}
    """
    today = date.today()
    out = defaultdict(int)

    if _is_multi_mode(db):
        # Build per (cid, day) role maps
        rows = db.execute("""
            SELECT day, carpool_id AS cid, user_id, role
            FROM entries
        """).fetchall()
        by = defaultdict(lambda: defaultdict(dict))  # {cid: {day: {user_id: role}}}
        for r in rows:
            d = _day_to_date(r["day"])
            if d > today:  # future excluded
                continue
            by[r["cid"]][d][r["user_id"]] = r["role"]
        for cid, daymap in by.items():
            for d, roles in daymap.items():
                if "D" not in roles.values():  # require at least one driver
                    continue
                if roles.get(user_id) == "R":
                    out[cid] += 1
    else:
        # Legacy: use members/member_key
        # Infer member_key from username (best-effort)
        uname = (session.get("username") or "").strip().lower()
        key = None
        rows = db.execute("SELECT key, name FROM members").fetchall()
        for r in rows:
            if (r["name"] or "").strip().lower() == uname:
                key = r["key"]
                break

        rows = db.execute("SELECT day, member_key, role FROM entries").fetchall()
        by_day = defaultdict(dict)
        for r in rows:
            d = _day_to_date(r["day"])
            if d > today:
                continue
            by_day[d][r["member_key"]] = r["role"]
        for d, roles in by_day.items():
            if "D" not in roles.values():
                continue
            if key and roles.get(key) == "R":
                out["legacy"] += 1

    return dict(out)

@accountbp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    db = get_db()
    user_id = session.get("user_id")
    username = (session.get("username") or "").strip()

    # Password change
    if request.method == "POST" and request.form.get("action") == "change_password":
        pw1 = request.form.get("pw1", "")
        pw2 = request.form.get("pw2", "")
        if not pw1 or not pw2 or pw1 != pw2:
            flash("Passwords must be entered and match.", "error")
            return redirect(url_for("accountbp.account"))
        db.execute(
            "UPDATE users SET password_hash=? WHERE username=?",
            (sha256(pw1.encode()).hexdigest(), username)
        )
        db.commit()
        flash("Password updated.")
        return redirect(url_for("accountbp.account"))

    # Save global prefs
    if request.method == "POST" and request.form.get("action") == "save_globals":
        try:
            gas_price = float(request.form.get("gas_price", "4.78") or "4.78")
            avg_mpg   = float(request.form.get("avg_mpg", "22") or "22")
        except ValueError:
            flash("Please enter valid numbers for Gas price and Avg MPG.", "error")
            return redirect(url_for("accountbp.account"))

        if _is_multi_mode(db):
            _save_global_prefs(db, user_id, gas_price, avg_mpg)
        else:
            try:
                legacy_mpr = float(request.form.get("legacy_mpr", "36") or "36")
            except ValueError:
                flash("Please enter a valid number for Miles per ride.", "error")
                return redirect(url_for("accountbp.account"))
            _save_global_prefs(db, user_id, gas_price, avg_mpg, legacy_mpr)
        flash("Preferences saved.")
        return redirect(url_for("accountbp.account"))

    # Save per-carpool MPRs
    if request.method == "POST" and request.form.get("action") == "save_mprs":
        mpr_map = {}
        for k, v in request.form.items():
            if k.startswith("mpr_"):
                try:
                    cid = int(k.split("_", 1)[1])
                    mpr_map[cid] = float(v or "36")
                except Exception:
                    continue
        if mpr_map:
            _save_mprs(db, user_id, mpr_map)
            flash("Miles per ride updated.")
        return redirect(url_for("accountbp.account"))

    # Load prefs
    gas_price, avg_mpg, legacy_mpr = _get_global_prefs(db, user_id)
    carpool_mprs = _get_carpool_mprs(db, user_id)  # [] in legacy

    # Compute rides per carpool with the new rule, then miles & savings
    rides_by_cid = _count_rides_by_carpool(db, user_id)
    total_miles = 0.0
    # multi-carpool
    for r in carpool_mprs:
        rid = rides_by_cid.get(r["id"], 0)
        total_miles += rid * r["mpr"]
    # legacy fallback
    if not carpool_mprs:
        rid = rides_by_cid.get("legacy", 0)
        total_miles += rid * legacy_mpr

    gallons = (total_miles / avg_mpg) if avg_mpg else 0.0
    gas_savings = gallons * gas_price

    # Template
    tmpl = """
    {% extends 'BASE_TMPL' %}{% block content %}
      <h3>Account</h3>

      <div class="grid" style="gap:12px;">
        <!-- Global prefs -->
        <form method="post" class="card">
          <input type="hidden" name="action" value="save_globals">
          <h5>Fuel settings</h5>
          <div class="row g-3">
            <div class="col-6">
              <label class="form-label">Gas price ($/gal)
                <input class="form-control" name="gas_price" value="{{ gas_price }}" inputmode="decimal" required>
              </label>
            </div>
            <div class="col-6">
              <label class="form-label">Average MPG
                <input class="form-control" name="avg_mpg" value="{{ avg_mpg }}" inputmode="decimal" required>
              </label>
            </div>

            {% if not is_multi %}
            <div class="col-6">
              <label class="form-label">Miles per ride (legacy)
                <input class="form-control" name="legacy_mpr" value="{{ legacy_mpr }}" inputmode="decimal" required>
              </label>
            </div>
            {% endif %}
          </div>
          <button class="btn btn-primary mt-2">Save</button>
        </form>

        {% if is_multi %}
        <!-- Per-carpool miles per ride -->
        <form method="post" class="card">
          <input type="hidden" name="action" value="save_mprs">
          <h5>Miles per ride by carpool</h5>
          <div class="table-scroll">
            <table class="table">
              <thead><tr><th>Carpool</th><th style="width:220px;">Miles per ride</th></tr></thead>
              <tbody>
                {% for r in carpool_mprs %}
                  <tr>
                    <td>{{ r.name }}</td>
                    <td>
                      <input class="form-control" name="mpr_{{ r.id }}" value="{{ r.mpr }}" inputmode="decimal" required>
                    </td>
                  </tr>
                {% endfor %}
                {% if not carpool_mprs %}
                  <tr><td colspan="2" class="muted">You aren't in any carpools yet.</td></tr>
                {% endif %}
              </tbody>
            </table>
          </div>
          <button class="btn btn-primary mt-2">Save</button>
        </form>
        {% endif %}

        <!-- Stats summary (uses new credit-day rule) -->
        <div class="card">
          <h5>Your summary</h5>
          <p class="muted">Miles are estimated as (rides × miles-per-ride) per carpool, only counting past/today days that had a driver.</p>
          <div><strong>Total miles:</strong> {{ total_miles|round(2) }}</div>
          <div><strong>Gas savings (est.):</strong> ${{ "%.2f"|format(gas_savings) }}</div>
        </div>

        <!-- Password -->
        <form method="post" class="card">
          <h5>Change password</h5>
          <input type="hidden" name="action" value="change_password">
          <div class="row g-3">
            <div class="col-6">
              <label class="form-label">New password
                <input class="form-control" type="password" name="pw1" required>
              </label>
            </div>
            <div class="col-6">
              <label class="form-label">Confirm password
                <input class="form-control" type="password" name="pw2" required>
              </label>
            </div>
          </div>
          <button class="btn btn-secondary mt-2">Change password</button>
        </form>
      </div>
    {% endblock %}
    """
    return render_template_string(
        tmpl,
        BASE_TMPL=BASE_TMPL,
        is_multi=_is_multi_mode(db),
        gas_price=gas_price, avg_mpg=avg_mpg, legacy_mpr=legacy_mpr,
        carpool_mprs=carpool_mprs,
        total_miles=total_miles, gas_savings=gas_savings,
    )
