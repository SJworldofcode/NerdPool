# routes_today.py
from flask import Blueprint, request, render_template_string, redirect, url_for, session, flash
from flask_login import current_user
from datetime import date, datetime, timedelta
from collections import defaultdict

from constants import ROLE_CHOICES
from templates import TODAY_TMPL
from db import get_db
from auth import login_required

todaybp = Blueprint("todaybp", __name__)

def parse_day(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return date.today()

def day_to_date(val) -> date:
    if isinstance(val, date):
        return val
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
    return db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,)
    ).fetchone() is not None

def _has_column(db, table: str, col: str) -> bool:
    try:
        cols = {r["name"] for r in db.execute(f"PRAGMA table_info({table})").fetchall()}
        return col in cols
    except Exception:
        return False

def _is_multi_mode(db) -> bool:
    return (
        _has_table(db, "carpool_memberships")
        and _has_column(db, "entries", "carpool_id")
        and _has_column(db, "entries", "user_id")
        and current_user.is_authenticated
    )

# ------------ CREDIT RULE (matching CESpool exactly) ------------
def compute_credits_all(rows, who_field: str = "who", cutoff_date: date = None):
    """
    Credits calculation rules:
      - ONLY days with exactly 1 driver are counted.
      - Driver: +1 per Rider
      - Rider:  -1
      - Off:     0
      - Future days (relative to calendar today) are IGNORED.
    rows = [{'day':..., 'who':..., 'role':...}]
    cutoff_date: if provided, excludes days > cutoff_date (applied *after* today check)
    """
    credits = defaultdict(int)
    by_day = defaultdict(dict)
    today_limit = date.today()

    for e in rows:
        d = day_to_date(e["day"])
        who = e[who_field]
        by_day[d][who] = e["role"]

    for d in sorted(by_day.keys()):
        # Rule: Only past days and today (calendar today).
        # Future dates should not change credits.
        if d > today_limit:
            continue

        if cutoff_date is not None and d > cutoff_date:
            continue

        roles = by_day[d]
        drivers = [w for w, r in roles.items() if r == "D"]
        riders = [w for w, r in roles.items() if r == "R"]
        
        # Rule: ONLY days with exactly 1 driver will be used to calc credits.
        if len(drivers) != 1:
            continue
            
        for drv in drivers:
            credits[drv] += len(riders)
        for r in riders:
            credits[r] -= 1
    return dict(credits)
# ----------------------------------------------

def find_last_driver(db, *, multi: bool, cid: int | None, cutoff_day: date):
    if multi:
        rows = db.execute(
            "SELECT day, user_id AS who, role FROM entries WHERE carpool_id=?",
            (cid,)
        ).fetchall()
    else:
        rows = db.execute("SELECT day, member_key AS who, role FROM entries").fetchall()

    last_day, last_driver = None, None
    for e in rows:
        d = day_to_date(e["day"])
        if d >= cutoff_day:
            continue
        if e["role"] == "D" and (last_day is None or d > last_day):
            last_day, last_driver = d, e["who"]
    return last_driver

def suggest_driver(db, selected_day: date, roles_today: dict, *, multi: bool, cid: int | None):
    active = [w for w, r in roles_today.items() if r != "O"]
    if len(active) < 2:
        return None

    if multi:
        rows_prev = db.execute(
            "SELECT day, user_id AS who, role FROM entries WHERE carpool_id=?",
            (cid,)
        ).fetchall()
    else:
        rows_prev = db.execute("SELECT day, member_key AS who, role FROM entries").fetchall()
    rows_prev = [r for r in rows_prev if day_to_date(r["day"]) < selected_day]

    credits = compute_credits_all(rows_prev, who_field="who")
    filtered = {w: credits.get(w, 0) for w in active}
    min_score = min(filtered.values()) if filtered else 0
    candidates = [w for w, sc in filtered.items() if sc == min_score]
    if len(candidates) == 1:
        return candidates[0]

    last_drv = find_last_driver(db, multi=multi, cid=cid, cutoff_day=selected_day)

    if multi:
        rows = db.execute(
            """
            SELECT user_id AS who, display_name
            FROM carpool_memberships
            WHERE carpool_id=? AND active=1
            ORDER BY display_name
            """,
            (cid,)
        ).fetchall()
        order = [r["who"] for r in rows if r["who"] in active]
    else:
        rows = db.execute(
            "SELECT key AS who, name AS display_name FROM members WHERE active=1 ORDER BY name"
        ).fetchall()
        order = [r["who"] for r in rows if r["who"] in active]

    if last_drv in order:
        start = (order.index(last_drv) + 1) % len(order)
        for i in range(len(order)):
            pick = order[(start + i) % len(order)]
            if pick in candidates:
                return pick

    for w in order:
        if w in candidates:
            return w
    return sorted(candidates, key=lambda x: str(x))[0] if candidates else None

@todaybp.route("/switch", methods=["POST"])
@login_required
def switch():
    db = get_db()
    uid = int(current_user.id)
    cid_post = request.form.get("carpool_id")
    
    # Verify membership
    row = db.execute("""
        SELECT c.id, c.name
        FROM carpools c
        JOIN carpool_memberships cm ON cm.carpool_id=c.id
        WHERE c.id=? AND cm.user_id=? AND cm.active=1 AND c.active=1
    """, (cid_post, uid)).fetchone()
    
    if row:
        session["carpool_id"] = int(row["id"])
        session["carpool_name"] = row["name"]
        flash(f"Switched to {row['name']}.")
    else:
        flash(f"Invalid carpool selection.", "error")
        
    return redirect(url_for("todaybp.today"))

@todaybp.route("/")
@login_required
def root():
    return redirect(url_for("todaybp.today"))

@todaybp.route("/today", methods=["GET", "POST"])
@login_required
def today():
    db = get_db()
    multi = _is_multi_mode(db)
    uid = int(current_user.id)

    selected_day = parse_day(
        (request.args.get("day") if request.method == "GET" else request.form.get("day"))
        or date.today().isoformat()
    )

    cid = session.get("carpool_id") if multi else None
    if multi and not cid:
        # Auto-select first if available, else show empty state
        first = db.execute("""
            SELECT c.id, c.name
            FROM carpools c
            JOIN carpool_memberships cm ON cm.carpool_id=c.id
            WHERE cm.user_id=? AND cm.active=1 AND c.active=1
            ORDER BY c.name LIMIT 1
        """, (uid,)).fetchone()
        if first:
            session["carpool_id"] = int(first["id"])
            session["carpool_name"] = first["name"]
            cid = int(first["id"])
        else:
            return render_template_string(
                TODAY_TMPL,
                selected_day=selected_day.isoformat(),
                members=[], roles={}, credits={},
                suggestion_name=None, driver_is_explicit=False,
                can_edit=False, no_carpool=True,
                multi=multi, carpool_options=[]
            )

    # Members + today's roles
    if multi:
        members = db.execute("""
            SELECT cm.user_id, cm.member_key, cm.display_name
            FROM carpool_memberships cm
            WHERE cm.carpool_id=? AND cm.active=1
            ORDER BY cm.display_name
        """, (cid,)).fetchall()
        existing = {
            r["user_id"]: r["role"]
            for r in db.execute(
                "SELECT user_id, role FROM entries WHERE carpool_id=? AND day LIKE ?",
                (cid, f"{selected_day.isoformat()}%",)
            ).fetchall()
        }
        roles_form = {m["user_id"]: existing.get(m["user_id"], "R") for m in members}
    else:
        members = db.execute(
            "SELECT key AS member_key, name AS display_name FROM members WHERE active=1 ORDER BY key"
        ).fetchall()
        existing = {
            r["member_key"]: r["role"]
            for r in db.execute(
                "SELECT member_key, role FROM entries WHERE day LIKE ?",
                (f"{selected_day.isoformat()}%",)
            ).fetchall()
        }
        roles_form = {m["member_key"]: existing.get(m["member_key"], "R") for m in members}

    # Lock old days
    can_edit = not (selected_day <= (date.today() - timedelta(days=7)) and not session.get("is_admin"))

    # Save roles
    if request.method == "POST" and request.form.get("action") == "save_roles":
        if not can_edit:
            flash("Editing locked for days older than 7 days (admin only).", "error")
            return redirect(url_for("todaybp.today", day=selected_day.isoformat()))

        if multi:
            posted = {}
            for m in members:
                field = f"u{m['user_id']}"
                val = request.form.get(field, "R")
                posted[m["user_id"]] = val
        else:
            posted = {m["member_key"]: request.form.get(m["member_key"], "R") for m in members}

        if not set(posted.values()).issubset(ROLE_CHOICES):
            return ("Bad role value", 400)

        writes = [(who, role) for who, role in posted.items() if existing.get(who) != role]
        if not writes:
            flash("No changes to save.")
            return redirect(url_for("todaybp.today", day=selected_day.isoformat()))

        if multi:
            for user_id, role in writes:
                # Fetch the actual member_key from carpool_memberships
                mk_row = db.execute(
                    "SELECT member_key FROM carpool_memberships WHERE carpool_id=? AND user_id=?",
                    (cid, user_id)
                ).fetchone()
                
                if mk_row and mk_row["member_key"]:
                    member_key = mk_row["member_key"]
                else:
                    member_key = f"u{user_id}"
                
                db.execute(
                    """
                    INSERT INTO entries(carpool_id, day, user_id, member_key, role, update_user, update_ts, update_date)
                    VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP, DATE('now'))
                    ON CONFLICT(carpool_id, day, user_id) DO UPDATE SET
                      role=excluded.role,
                      member_key=excluded.member_key,
                      update_user=excluded.update_user,
                      update_ts=CURRENT_TIMESTAMP,
                      update_date=DATE('now')
                    """,
                    (cid, selected_day.isoformat(), user_id, member_key, role, session.get('username', 'unknown'))
                )
        else:
            for member_key, role in writes:
                db.execute(
                    """
                    INSERT INTO entries(day, member_key, role, update_user, update_ts, update_date)
                    VALUES(?,?,?,?,CURRENT_TIMESTAMP, DATE('now'))
                    ON CONFLICT(day, member_key) DO UPDATE SET
                      role=excluded.role,
                      update_user=excluded.update_user,
                      update_ts=CURRENT_TIMESTAMP,
                      update_date=DATE('now')
                    """,
                    (selected_day.isoformat(), member_key, role, session.get('username', 'unknown'))
                )
        db.commit()
        flash("Saved.")
        return redirect(url_for("todaybp.today", day=selected_day.isoformat()))

    # Credits calculation
    # - For past/future dates: show credits BEFORE that day (matches CESpool)
    # - For TODAY: include today's entries so changes are reflected immediately
    if multi:
        rows_prev = db.execute(
            "SELECT day, user_id AS who, role FROM entries WHERE carpool_id=?",
            (cid,)
        ).fetchall()
    else:
        rows_prev = db.execute("SELECT day, member_key AS who, role FROM entries").fetchall()
    
    # Credits calculation:
    # - Always include the selected day so the user sees the effect of their changes immediately.
    # - compute_credits_all will internally filter out any days > date.today() (calendar future),
    #   ensuring future plans don't affect the balance.
    rows_filtered = [r for r in rows_prev if day_to_date(r["day"]) <= selected_day]
    
    credits = compute_credits_all(rows_filtered, who_field="who", cutoff_date=None)

    active = [k for k, v in roles_form.items() if v != "O"]
    no_carpool_day = len(active) < 2

    explicit_driver = next((k for k, v in roles_form.items() if v == "D"), None)
    suggestion_name = None
    driver_is_explicit = False

    if not no_carpool_day:
        if explicit_driver is not None:
            if multi:
                name = db.execute(
                    "SELECT display_name FROM carpool_memberships WHERE carpool_id=? AND user_id=?",
                    (cid, explicit_driver)
                ).fetchone()
                suggestion_name = (name["display_name"] if name else str(explicit_driver))
            else:
                name = db.execute("SELECT name FROM members WHERE key=?", (explicit_driver,)).fetchone()
                suggestion_name = (name["name"] if name else str(explicit_driver))
            driver_is_explicit = True
        else:
            pick = suggest_driver(db, selected_day, roles_form, multi=multi, cid=cid)
            if pick is not None:
                if multi:
                    name = db.execute(
                        "SELECT display_name FROM carpool_memberships WHERE carpool_id=? AND user_id=?",
                        (cid, pick)
                    ).fetchone()
                    suggestion_name = (name["display_name"] if name else str(pick))
                else:
                    name = db.execute("SELECT name FROM members WHERE key=?", (pick,)).fetchone()
                    suggestion_name = (name["name"] if name else str(pick))

    if multi:
        members_ctx = [{"user_id": m["user_id"], "member_key": m["member_key"], "display_name": m["display_name"]} for m in members]
    else:
        members_ctx = [{"key": m["member_key"], "name": m["display_name"]} for m in members]

    if multi:
        carpool_options = db.execute("""
            SELECT c.id, c.name
            FROM carpools c
            JOIN carpool_memberships cm ON cm.carpool_id=c.id
            WHERE cm.user_id=? AND cm.active=1 AND c.active=1
            ORDER BY c.name
        """, (uid,)).fetchall()

    return render_template_string(
        TODAY_TMPL,
        selected_day=selected_day.isoformat(),
        members=members_ctx,
        roles=roles_form,
        credits=credits,
        suggestion_name=suggestion_name,
        driver_is_explicit=driver_is_explicit,
        can_edit=can_edit,
        no_carpool=no_carpool_day,
        multi=multi,
        carpool_options=carpool_options
    )
