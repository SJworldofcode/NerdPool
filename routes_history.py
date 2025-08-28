# routes_history.py
from flask import Blueprint, render_template_string, abort
from templates import HISTORY_TMPL, STATS_TMPL
from constants import MEMBERS
from db import get_db
from auth import login_required

from flask import render_template_string, request   # <-- ensure this is imported
from datetime import datetime, date
from collections import defaultdict

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

@historybp.route("/history")
@login_required
def history():
    db = get_db()
    rows = db.execute("SELECT day, member_key, role FROM entries").fetchall()

    # Build per-day role map
    by_day = defaultdict(lambda: {"CA": None, "ER": None, "SJ": None})
    for r in rows:
        d = _day_to_date(r["day"])
        by_day[d][r["member_key"]] = r["role"]

    # Filters from query string
    start  = (request.args.get("start")  or "").strip()
    end    = (request.args.get("end")    or "").strip()
    member = (request.args.get("member") or "").strip().upper()
    role   = (request.args.get("role")   or "").strip().upper()

    start_d = datetime.strptime(start, "%Y-%m-%d").date() if start else None
    end_d   = datetime.strptime(end,   "%Y-%m-%d").date() if end   else None

    # Build formatted rows with Rider defaults and apply filters
    rows_fmt = []
    for d in sorted(by_day.keys(), reverse=True):
        if start_d and d < start_d: continue
        if end_d and d > end_d:     continue

        roles = by_day[d]
        ca = roles["CA"] if roles["CA"] is not None else "R"
        er = roles["ER"] if roles["ER"] is not None else "R"
        sj = roles["SJ"] if roles["SJ"] is not None else "R"

        # Apply member/role filters
        if member:
            val = {"CA": ca, "ER": er, "SJ": sj}.get(member)
            # If the selected member doesn't match the selected role (when provided), skip
            if role in ("D","R","O") and val != role:
                continue
        elif role in ("D","R","O"):
            # No member filter; include only days where at least one member matches the role
            if not (ca == role or er == role or sj == role):
                continue

        rows_fmt.append({
            "day_fmt": f"{d:%a} {d:%Y-%m-%d}",
            "CA": ca, "ER": er, "SJ": sj
        })

    # Inline template with filter controls (so we don't depend on HISTORY_TMPL here)
    tmpl = """
    {% extends "BASE_TMPL" %}{% block content %}
      <h3>History</h3>
    
      <form class="row g-2 align-items-end mb-3" method="get">
        <div class="col-auto">
          <label class="form-label">From</label>
          <input class="form-control" type="date" name="start" value="{{ request.args.get('start','') }}">
        </div>
        <div class="col-auto">
          <label class="form-label">To</label>
          <input class="form-control" type="date" name="end" value="{{ request.args.get('end','') }}">
        </div>
        
        <div class="col-auto">
          <button class="btn btn-primary">Filter</button>
          <a class="btn btn-secondary" href="{{ url_for('historybp.history') }}">Reset</a>
        </div>
      </form>

      <div class="table-scroll">
        <table class="table table-sm table-sticky">
          <thead><tr><th>Date</th><th>Christian</th><th>Eric</th><th>Sean</th></tr></thead>
          <tbody>
            {% for r in rows %}
            <tr>
              <td>{{ r['day_fmt'] }}</td>
              <td>{{ r['CA'] or '' }}</td>
              <td>{{ r['ER'] or '' }}</td>
              <td>{{ r['SJ'] or '' }}</td>
            </tr>
            {% endfor %}
            {% if not rows %}
              <tr><td colspan="4" class="text-center text-muted">No results</td></tr>
            {% endif %}
          </tbody>
        </table>
      </div>
    {% endblock %}
    """
    from templates import BASE_TMPL
    return render_template_string(tmpl, rows=rows_fmt, BASE_TMPL=BASE_TMPL)

@historybp.route("/stats/<member_key>")
@login_required
def member_stats(member_key):
    if member_key not in MEMBERS:
        abort(404)
    db = get_db()
    counts = db.execute(
        "SELECT role, COUNT(*) AS n FROM entries WHERE member_key=? GROUP BY role",
        (member_key,)
    ).fetchall()
    counts = {r["role"]: r["n"] for r in counts}
    return render_template_string(STATS_TMPL, member_key=member_key, member_name=MEMBERS[member_key], counts=counts)
