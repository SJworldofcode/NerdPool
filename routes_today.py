# routes_today.py
from flask import Blueprint, request, render_template_string, redirect, url_for, session, flash
from datetime import date, datetime, timedelta
from collections import defaultdict

from constants import MEMBERS, MEMBER_ORDER, ROLE_CHOICES
from templates import TODAY_TMPL
from db import get_db
from auth import login_required

todaybp = Blueprint("todaybp", __name__)

# ---------- Date helpers ----------

def parse_day(s: str) -> date:
    """Parse an ISO yyyy-mm-dd string from the form/query; fallback to today."""
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return date.today()

def day_to_date(val) -> date:
    """
    Normalize DB 'day' values into a date object.
    Supports:
      - ISO 'YYYY-MM-DD...'
      - 'Jul 12, 2023, 12:00:00 AM' (commas stripped first)
    Falls back to today on parse failure (rare).
    """
    if isinstance(val, date):
        return val
    s = str(val or "")
    # Try ISO first
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        pass
    # Try viewer-style (commas removed)
    try:
        return datetime.strptime(s.replace(",", ""), "%b %d %Y %I:%M:%S %p").date()
    except Exception:
        pass
    return date.today()

# ---------- Credit & suggestion logic (single unified carpool) ----------

def compute_credits_all(entries):
    """
    Compute credits across the ONE unified carpool:
      - Driver: +1 per rider that same day
      - Rider:  -1
      - Off:     0
    Returns a dict { member_key -> credits } across *all* history provided.
    """
    credits = defaultdict(int)
    by_day = defaultdict(dict)
    for e in entries:
        d = day_to_date(e["day"])
        by_day[d][e["member_key"]] = e["role"]

    for d in sorted(by_day.keys()):
        roles = by_day[d]
        drivers = [m for m, r in roles.items() if r == "D"]
        riders  = [m for m, r in roles.items() if r == "R"]
        if not drivers and not riders:
            continue
        for drv in drivers:
            credits[drv] += len(riders)
        for r in riders:
            credits[r] -= 1
    return dict(credits)

def find_last_driver_overall(db, cutoff_day: date):
    """
    Find the last driver strictly before cutoff_day to help with rotation tie-breaks.
    """
    rows = db.execute("SELECT day, member_key, role FROM entries").fetchall()
    by_day = {}
    for e in rows:
        d = day_to_date(e["day"])
        if d >= cutoff_day:
            continue
        by_day.setdefault(d, {})[e["member_key"]] = e["role"]

    last_day, last_driver = None, None
    for d in sorted(by_day.keys()):
        driver = next((m for m, r in by_day[d].items() if r == "D"), None)
        if driver is not None and (last_day is None or d > last_day):
            last_day, last_driver = d, driver
    return last_driver

def suggest_driver(db, selected_day: date, roles_today: dict):
    """
    Suggest a driver for selected_day using unified credits:
      1) Lowest credits among today's active (not Off)
      2) If tie, rotate from last driver then use MEMBER_ORDER
    Returns member_key or None if <2 active (No Carpool Today).
    """
    active = [m for m, r in roles_today.items() if r != "O"]
    if len(active) < 2:
        return None

    rows = db.execute("SELECT day, member_key, role FROM entries").fetchall()
    rows = [r for r in rows if day_to_date(r["day"]) < selected_day]
    credits = compute_credits_all(rows)

    filtered = {m: credits.get(m, 0) for m in active}
    min_score = min(filtered.values()) if filtered else 0
    candidates = [m for m, sc in filtered.items() if sc == min_score]
    if len(candidates) == 1:
        return candidates[0]

    # Tie-break with last driver rotation, then MEMBER_ORDER
    last_driver = find_last_driver_overall(db, selected_day)
    order = [m for m in MEMBER_ORDER if m in active]
    if last_driver in order:
        start = (order.index(last_driver) + 1) % len(order)
        for i in range(len(order)):
            pick = order[(start + i) % len(order)]
            if pick in candidates:
                return pick
    for m in order:
        if m in candidates:
            return m
    return sorted(candidates)[0] if candidates else None

# ---------- Routes ----------

@todaybp.route("/")
@login_required
def root():
    return redirect(url_for("todaybp.today"))

@todaybp.route("/today", methods=["GET", "POST"])
@login_required
def today():
    db = get_db()
    members = db.execute("SELECT key, name FROM members WHERE active=1 ORDER BY key").fetchall()

    selected_day = parse_day(
        (request.args.get("day") if request.method == "GET" else request.form.get("day"))
        or date.today().isoformat()
    )

    existing = {r["member_key"]: r["role"] for r in db.execute(
        "SELECT member_key, role FROM entries WHERE day LIKE ?",  # LIKE to be format-agnostic
        (f"{selected_day.isoformat()}%",)
    ).fetchall()}

    # Default roles: 'R' (Rider) for new/future days (assume carpool is in play)
    roles_form = {m["key"]: existing.get(m["key"], "R") for m in members}

    # Editing lock: only admins can modify entries older than 7 days
    can_edit = True
    if selected_day <= (date.today() - timedelta(days=7)) and not session.get("is_admin"):
        can_edit = False

    # Handle POST (saves)
    if request.method == "POST":
        if not can_edit:
            flash("Editing locked for days older than 7 days (admin only).", "error")
            return redirect(url_for("todaybp.today", day=selected_day.isoformat()))

        # What the user chose
        roles_posted = {m["key"]: request.form.get(m["key"], "R") for m in members}
        if not set(roles_posted.values()).issubset(ROLE_CHOICES):
            return ("Bad role value", 400)

        # Load current (if any) for this day; we already fetched 'existing' above,
        # so use that to avoid re-query and only write changes.
        writes = []
        for key, role in roles_posted.items():
            if existing.get(key) != role:
                writes.append((key, role))

        if not writes:
            flash("No changes to save.")
            return redirect(url_for("todaybp.today", day=selected_day.isoformat()))

        for key, role in writes:
            db.execute(
                "INSERT INTO entries(day, member_key, role, update_user, update_ts, update_date) "
                "VALUES(?,?,?,?,CURRENT_TIMESTAMP, DATE('now')) "
                "ON CONFLICT(day, member_key) DO UPDATE SET "
                "role=excluded.role, "
                "update_user=excluded.update_user, "
                "update_ts=CURRENT_TIMESTAMP, "
                "update_date=DATE('now')",
                (selected_day.isoformat(), key, role, session.get('username', 'unknown'))
            )

        db.commit()
        flash("Saved.")
        return redirect(url_for("todaybp.today", day=selected_day.isoformat()))

    # Credits up to yesterday (exclude the selected day); filter in Python for date-format safety
    rows_prev = db.execute("SELECT day, member_key, role FROM entries").fetchall()
    rows_prev = [r for r in rows_prev if day_to_date(r["day"]) < selected_day]
    credits = compute_credits_all(rows_prev)

    # Determine "No Carpool Today" and suggestion
    active = [k for k, v in roles_form.items() if v != "O"]
    no_carpool = len(active) < 2

    explicit_driver = next((k for k, v in roles_form.items() if v == "D"), None)
    suggestion_name = None
    driver_is_explicit = False
    if not no_carpool:
        if explicit_driver:
            suggestion_name = MEMBERS.get(explicit_driver, explicit_driver)
            driver_is_explicit = True
        else:
            pick = suggest_driver(db, selected_day, roles_form)
            if pick:
                suggestion_name = MEMBERS.get(pick, pick)

    return render_template_string(
        TODAY_TMPL,
        selected_day=selected_day.isoformat(),
        members=members,
        roles=roles_form,
        credits=credits,                 # shown as "(X credits)" next to each name
        suggestion_name=suggestion_name, # "___ should drive" / "is driving"
        driver_is_explicit=driver_is_explicit,
        can_edit=can_edit,
        no_carpool=no_carpool,           # renders the "No Carpool Today" banner
    )
