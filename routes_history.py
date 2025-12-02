# routes_history.py
from flask import Blueprint, render_template_string, request, abort
from datetime import datetime, date
from collections import defaultdict

from db import get_db
from auth import login_required
from templates import STATS_TMPL

historybp = Blueprint("historybp", __name__)

def _day_to_date(val) -> date:
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

def _is_multi_mode(db, session) -> bool:
    return (
        _has_table(db, "carpool_memberships")
        and _has_column(db, "entries", "carpool_id")
        and _has_column(db, "entries", "user_id")
        and bool(session.get("carpool_id"))
    )

@historybp.route("/history")
@login_required
def history():
    from flask import session, url_for
    db = get_db()
    multi = _is_multi_mode(db, session)
    cid = session.get("carpool_id") if multi else None

    start  = (request.args.get("start") or "").strip()
    end    = (request.args.get("end") or "").strip()
    start_d = datetime.strptime(start, "%Y-%m-%d").date() if start else None
    end_d   = datetime.strptime(end,   "%Y-%m-%d").date() if end   else None

    if multi:
        members = db.execute("""
            SELECT user_id AS who, display_name AS label
            FROM carpool_memberships
            WHERE carpool_id=? AND active=1
            ORDER BY display_name
        """, (cid,)).fetchall()
        headers = [(m["who"], m["label"]) for m in members]
        rows = db.execute("""
            SELECT day, user_id AS who, role
            FROM entries
            WHERE carpool_id=?
        """, (cid,)).fetchall()
    else:
        members = db.execute("""
            SELECT key AS who, name AS label
            FROM members
            WHERE active=1
            ORDER BY key
        """).fetchall()
        headers = [(m["who"], m["label"]) for m in members]
        rows = db.execute("SELECT day, member_key AS who, role FROM entries").fetchall()

    by_day = defaultdict(dict)  # {date: { who: role }}
    for r in rows:
        d = _day_to_date(r["day"])
        if start_d and d < start_d: continue
        if end_d and d > end_d:     continue
        by_day[d][r["who"]] = r["role"]

    out_rows = []
    for d in sorted(by_day.keys(), reverse=True):
        role_map = by_day[d]
        out_rows.append({
            "day_fmt": f"{d:%a} {d:%Y-%m-%d}",
            "roles": {who: role_map.get(who, "R") for who, _label in headers}
        })

    carpool_options = []
    if multi:
        uid = session.get("user_id")
        carpool_options = db.execute("""
            SELECT c.id, c.name
            FROM carpools c
            JOIN carpool_memberships cm ON cm.carpool_id=c.id
            WHERE cm.user_id=? AND cm.active=1
            ORDER BY c.name
        """, (uid,)).fetchall()

    tmpl = """
    {% extends "BASE_TMPL" %}{% block content %}
      <h3>History</h3>
      
      <!-- Carpool Context -->
      {% if session.get('carpool_name') %}
        <div style="margin-bottom: 14px; padding: 10px; background: var(--panel); border-radius: 10px; border: 1px solid var(--border);">
          <span class="muted" style="font-size: .9rem;">Displaying data for:</span>
          <strong style="color: var(--accent); margin-left: 6px;">{{ session.get('carpool_name') }}</strong>
        </div>
      {% endif %}

      <form class="row g-2 align-items-end mb-3" method="get">
        <div class="col-auto">
          <label class="form-label">From</label>
          <input class="form-control" type="date" name="start" value="{{ request.args.get('start','') }}" pattern=r"\d{4}-\d{2}-\d{2}">
        </div>
        <div class="col-auto">
          <label class="form-label">To</label>
          <input class="form-control" type="date" name="end" value="{{ request.args.get('end','') }}" pattern=r"\d{4}-\d{2}-\d{2}">
        </div>
        <div class="col-auto">
          <button class="btn btn-primary">Filter</button>
          <a class="btn btn-secondary" href="{{ url_for('historybp.history') }}">Reset</a>
        </div>
      </form>

      <div class="table-scroll">
        <table class="table table-sm table-sticky align-middle">
          <thead>
            <tr>
              <th>Date</th>
              {% for who, label in headers %}
                <th>
                  {{ label }}
                  <a class="badge" href="{{ url_for('historybp.member_stats', who=who) }}">stats</a>
                </th>
              {% endfor %}
            </tr>
          </thead>
          <tbody>
            {% for r in rows %}
              <tr>
                <td>{{ r['day_fmt'] }}</td>
                {% for who, label in headers %}
                  <td>{{ r['roles'].get(who, '') }}</td>
                {% endfor %}
              </tr>
            {% endfor %}
            {% if not rows %}
              <tr><td colspan="{{ 1 + headers|length }}" class="text-center text-muted">No results</td></tr>
            {% endif %}
          </tbody>
        </table>
      </div>
    {% endblock %}
    """
    from templates import BASE_TMPL
    return render_template_string(
        tmpl,
        BASE_TMPL=BASE_TMPL,
        headers=headers,
        rows=out_rows,
        multi=multi,
        carpool_options=carpool_options
    )

@historybp.route("/stats/<who>")
@login_required
def member_stats(who):
    db = get_db()
    from flask import session
    multi = _is_multi_mode(db, session)

    # int => user_id (multi); non-int => legacy member_key
    is_int = False
    try:
        _ = int(who); is_int = True
    except Exception:
        pass

    if multi and is_int:
        cid = session.get("carpool_id")
        user_id = int(who)
        counts = db.execute("""
            SELECT role, COUNT(*) AS n
            FROM entries
            WHERE carpool_id=? AND user_id=?
            GROUP BY role
        """, (cid, user_id)).fetchall()
        counts = {r["role"]: r["n"] for r in counts}
        row = db.execute("""
            SELECT display_name FROM carpool_memberships
            WHERE carpool_id=? AND user_id=?
        """, (cid, user_id)).fetchone()
        if not row: abort(404)
        return render_template_string(
            STATS_TMPL, member_key=f"u{user_id}", member_name=row["display_name"], counts=counts
        )

    member_key = who.upper()
    row = db.execute("SELECT name FROM members WHERE key=?", (member_key,)).fetchone()
    if not row: abort(404)
    counts = db.execute(
        "SELECT role, COUNT(*) AS n FROM entries WHERE member_key=? GROUP BY role",
        (member_key,)
    ).fetchall()
    counts = {r["role"]: r["n"] for r in counts}
    return render_template_string(STATS_TMPL, member_key=member_key, member_name=row["name"], counts=counts)
