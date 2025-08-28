# routes_account.py
from flask import Blueprint, render_template_string, session, request, redirect, url_for, flash
from datetime import date, datetime
from hashlib import sha256

from db import get_db
from auth import login_required
from constants import MILES_PER_RIDE, MEMBERS, GAS_PRICE, AVG_MPG
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

def _infer_member_key():
    # Prefer explicit member_key if already stored
    mk = (session.get("member_key") or "").strip().upper()
    if mk in MEMBERS:
        return mk
    # Fallback: infer from username
    uname = (session.get("username") or "").strip().lower()
    if uname:
        for k, v in MEMBERS.items():
            if v.strip().lower() == uname:
                session["member_key"] = k
                return k
    return None

@accountbp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    db = get_db()

    # --- Handle password change on POST ---
    if request.method == "POST":
        pw1 = request.form.get("pw1", "")
        pw2 = request.form.get("pw2", "")
        if not pw1 or not pw2:
            flash("Please enter and confirm a password.", "error")
            return redirect(url_for("accountbp.account"))
        if pw1 != pw2:
            flash("Passwords do not match.", "error")
            return redirect(url_for("accountbp.account"))

        username = (session.get("username") or "").strip()
        if not username:
            flash("Not logged in.", "error")
            return redirect(url_for("accountbp.account"))

        db.execute(
            "UPDATE users SET password_hash=? WHERE username=?",
            (sha256(pw1.encode()).hexdigest(), username)
        )
        db.commit()
        flash("Password updated.")
        return redirect(url_for("accountbp.account"))

    # --- Build stats (only days with a Driver, up to today) ---
    user_key = _infer_member_key()
    # If still unknown, show a one-time picker
    if not user_key:
        pick_tmpl = """
        {% extends 'BASE_TMPL' %}{% block content %}
          <h3>Account</h3>
          <div class="card">
            <h5>Who are you?</h5>
            <form method="post" action="{{ url_for('accountbp.account') }}">
              <label class="form-label">Member</label>
              <select name="member_key" class="form-select" required>
                {% for k, v in members.items() %}
                  <option value="{{k}}">{{k}} — {{v}}</option>
                {% endfor %}
              </select>
              <input type="hidden" name="pw1" value="">
              <input type="hidden" name="pw2" value="">
              <button class="btn btn-primary mt-2">Continue</button>
            </form>
          </div>
        {% endblock %}
        """
        # store pick if posted
        mk = (request.form.get("member_key") or "").strip().upper()
        if mk in MEMBERS:
            session["member_key"] = mk
            return redirect(url_for("accountbp.account"))
        return render_template_string(pick_tmpl, BASE_TMPL=BASE_TMPL, members=MEMBERS)

    # Pull all entries up to today (entries: day, member_key, role)
    rows = db.execute("SELECT day, member_key, role FROM entries WHERE day <= DATE('now')").fetchall()

    by_day = {}
    for r in rows:
        d = _day_to_date(r["day"])
        by_day.setdefault(d, {})[r["member_key"]] = r["role"]
    valid_days = {d: roles for d, roles in by_day.items() if "D" in roles.values()}

    drives = rides = offs = 0
    for roles in valid_days.values():
        role = roles.get(user_key)
        if role == "D": drives += 1
        elif role == "R": rides += 1
        elif role == "O": offs += 1

    miles = rides * MILES_PER_RIDE
    gallons = miles / AVG_MPG if AVG_MPG else 0
    gas_savings = gallons * GAS_PRICE

    tmpl = """
    {% extends 'BASE_TMPL' %}{% block content %}
      <h3>Account</h3>


        <div class="ms-3 card p-3 mb-3">
        <h3>Stats</h3>
            <div style="margin-left: 2em;">
                <p><strong>Drives: </strong> {{ drives }}</p>
                <p><strong>Rides: </strong> {{ rides }}</p>
                <p><strong>Off: </strong> {{ offs }}</p>
                <p><strong>Miles (est. as passenger): </strong> {{ miles }}</p>
                <p><strong>Gas Savings (est.): </strong>
                   ${{ "%.2f"|format(gas_savings) }}
                   <div style="margin-left: 2em;">
                    <p><i><small>( {{ miles }} ÷ {{ avg_mpg }} mpg × ${{ gas_price }}/gal and {{ miles_per_ride }} miles per day saved.</i></small>)
                    </p></div>
            </div
      </div>

      <form method="post" class="card">
        <h5>Change password</h5>
        <label>New password<br><input type="password" name="pw1" required></label><br><br>
        <label>Confirm password<br><input type="password" name="pw2" required></label><br><br>
        <button class="btn btn-primary">Change password</button>
      </form>
    {% endblock %}
    """
    return render_template_string(
        tmpl,
        BASE_TMPL=BASE_TMPL,
        drives=drives, rides=rides, offs=offs,
        miles=miles, gas_savings=gas_savings,
        avg_mpg=AVG_MPG, gas_price=GAS_PRICE, miles_per_ride=MILES_PER_RIDE
    )
