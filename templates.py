# templates.py

# ---------- Base layout (navbar + styles + flash handling) ----------
BASE_TMPL = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>NerdPool</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {
      --bg: #0b0c10;
      --panel: #15171d;
      --text: #e6e8ee;
      --muted: #97a3b6;
      --accent: #4f8cff;
      --accent-2: #2a6cf6;
      --danger: #ff6b6b;
      --ok: #24c38b;
      --warn: #f6c042;
      --card: #1b1e27;
      --border: #2a2f3a;
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; height: 100%; }
    body {
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji";
      color: var(--text);
      background: radial-gradient(1200px 800px at 0 -100px, #172033 0%, #0b0c10 50%);
    }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }

    .wrap { max-width: 1100px; margin: 0 auto; padding: 18px 16px 64px; }
.navbar { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px;
  background: rgba(15,17,23,.7); backdrop-filter: blur(6px);
  border:1px solid var(--border); border-radius:14px; padding:8px 10px; margin-bottom:16px; }
    .nav-left, .nav-right { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
    .nav-links { display:flex; align-items:center; gap:8px; }
    .burger { display:none; background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:8px; cursor:pointer; }
    .brand { font-weight: 700; letter-spacing: .2px; padding: 6px 10px; border-radius: 10px; background: var(--card); border: 1px solid var(--border);}
    .pill { padding: 6px 10px; border-radius: 999px; background: var(--card); border: 1px solid var(--border); color: var(--muted);}
    .btn { display: inline-block; padding: 8px 12px; border-radius: 10px; border: 1px solid var(--border); background: var(--panel); color: var(--text); cursor: pointer; }
    .btn:hover { background: #1f2430; }
    .btn-primary { background: linear-gradient(180deg, var(--accent), var(--accent-2)); border: 0; color: #fff; }
    .btn-danger { background: linear-gradient(180deg, #ff6b6b, #ff4040); border: 0; color: #fff; }
    .btn-secondary { background: #232734; }
    .btn-sm { padding: 5px 9px; font-size: .92rem; border-radius: 8px; }

    .card { background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 14px; }
    .grid { display: grid; gap: 12px; }
    .grid-2 { grid-template-columns: repeat(2, minmax(0,1fr)); }
    @media (max-width: 720px) {
  .nav-links { display:none; width:100%; flex-direction:column; align-items:flex-start; }
  .nav-links.show { display:flex; }
  .burger { display:inline-block; }
}

    .form-row { display: flex; gap: 10px; flex-wrap: wrap; }
    .form-label { display: block; color: var(--muted); font-size: .92rem; margin-bottom: 6px; }
    .form-control, .form-select, input[type="date"], input[type="text"], input[type="password"], input[type="number"] {
      width: 100%; background: #12141a; color: var(--text); border: 1px solid var(--border); border-radius: 10px; padding: 8px 10px;
    }
    .form-check { display: flex; align-items: center; gap: 8px; }

    .table { width: 100%; border-collapse: collapse; }
    .table th, .table td { padding: 8px 10px; border-bottom: 1px solid var(--border); }
    .table thead th { position: sticky; top: 0; background: #12141a; z-index: 1; }
    .table-scroll { overflow: auto; max-height: 70vh; border: 1px solid var(--border); border-radius: 10px; }

    .flash { padding: 10px 12px; border-radius: 10px; margin-bottom: 10px; }
    .flash-info { background: rgba(79,140,255,.12); border: 1px solid #3b6bd8; }
    .flash-error { background: rgba(255,107,107,.12); border: 1px solid #ff6b6b; }

    .muted { color: var(--muted); }
    .badge { display:inline-block; padding: 2px 7px; border-radius: 999px; font-size: .85rem; border: 1px solid var(--border); background: #141821; color: var(--muted);}
    .spacer { flex: 1; }
    .footer { margin-top: 18px; color: var(--muted); font-size: .9rem; text-align: center; }
    /* Callouts */
.callout {
  border: 1px solid var(--border);
  border-left-width: 5px;
  border-radius: 12px;
  padding: 10px 12px;
  margin-top: 10px;
  background: #12141a;
  box-shadow: 0 6px 18px rgba(0,0,0,.25);
}
.callout .title { font-size: .92rem; color: var(--muted); margin-bottom: 4px; }
.callout-info    { border-left-color: var(--accent);    background: linear-gradient(180deg, rgba(79,140,255,.14), rgba(18,20,26,1)); }
.callout-success { border-left-color: var(--ok);        background: linear-gradient(180deg, rgba(36,195,139,.14), rgba(18,20,26,1)); }
.callout-danger  { border-left-color: var(--danger);    background: linear-gradient(180deg, rgba(255,107,107,.14), rgba(18,20,26,1)); }

  </style>
</head>
<body>
  <div class="wrap">
<div class="navbar">
  <div class="nav-left">
    <button class="burger" id="burger" aria-label="menu">☰</button>
    <div class="brand">NerdPool</div>
  </div>
  <div class="nav-links" id="navLinks">
    {% if carpool_options and carpool_options|length > 1 %}
      <form method="post" action="{{ url_for('todaybp.switch') }}" style="display:inline;">
        <select name="carpool_id" onchange="this.form.submit()" class="form-select" style="width:auto; padding:5px 28px 5px 10px; font-size:.92rem; height:34px; display:inline-block; cursor:pointer;">
             {% for opt in carpool_options %}
               <option value="{{ opt['id'] }}" {{ 'selected' if session.get('carpool_id') == opt['id'] else '' }}>{{ opt['name'] }}</option>
             {% endfor %}
        </select>
      </form>
    {% endif %}

    <a class="btn btn-sm" href="{{ url_for('todaybp.today') }}">Schedule</a>
    {% if not is_admin %}
      <a class="btn btn-sm" href="{{ url_for('historybp.history') }}">History</a>
    {% endif %}
    {% if is_admin %}
      <a class="btn btn-sm" href="{{ url_for('adminbp.admin_dashboard') }}">Admin</a>
    {% endif %}

    <a class="btn btn-sm" href="{{ url_for('accountbp.account') }}">Account{% if session.get('username') %} ({{ session.get('username') }}){% endif %}</a>
    <a class="btn btn-sm btn-secondary" href="{{ url_for('authbp.logout') }}">Logout</a>
  </div>
</div>

<script>
  const burger = document.getElementById('burger');
  const nav = document.getElementById('navLinks');
  if (burger && nav) burger.onclick = () => nav.classList.toggle('show');
</script>


    {% with messages = get_flashed_messages(with_categories=True) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="flash {{ 'flash-error' if category=='error' else 'flash-info' }}">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    {% block content %}{% endblock %}
<!--
    <div class="footer">
      <span class="muted">Use the Switch button to change nerdpools. Manage users and memberships under Admin.</span>
    </div> -->
  </div>
</body>
</html>
"""

# ---------- Login ----------
LOGIN_TMPL = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Login — Carpool</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { margin:0; display:grid; place-items:center; min-height:100vh; background:#0b0c10; color:#e6e8ee; font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; }
    .card { width: min(420px, 92vw); background:#15171d; border:1px solid #2a2f3a; border-radius:14px; padding:18px; }
    .title { font-weight:700; margin-bottom: 12px;}
    .form-label { display:block; color:#97a3b6; font-size:.92rem; margin-bottom:6px;}
    .form-control { width:100%; background:#12141a; color:#e6e8ee; border:1px solid #2a2f3a; border-radius:10px; padding:9px 10px; }
    .btn { width:100%; margin-top: 12px; padding:10px 12px; border:0; border-radius:10px; background:linear-gradient(180deg,#4f8cff,#2a6cf6); color:#fff; cursor:pointer; }
    .muted { color:#97a3b6; font-size:.92rem; }
    .row { display:grid; gap:10px; }
    .form-check { display:flex; align-items:center; gap:8px; margin-top:6px; }
    .flash { margin-top:12px; padding:10px 12px; border-radius:10px; background:rgba(255,107,107,.12); border:1px solid #ff6b6b; }
  </style>
</head>
<body>
  <div class="card">
    <div class="title">Sign in</div>
    <form method="post">
      <label class="form-label">Username</label>
      <input class="form-control" name="username" autocomplete="username" required>
      <label class="form-label" style="margin-top:8px;">Password</label>
      <input class="form-control" name="password" type="password" autocomplete="current-password" required>
      <label class="form-check">
        <input type="checkbox" name="remember"> <span class="muted">Keep me signed in on this device</span>
      </label>
      <button class="btn">Sign in</button>
    </form>
    {% with messages = get_flashed_messages(with_categories=True) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="flash">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}
  </div>
</body>
</html>
"""

# ---------- Today (dynamic members; works for single- or multi-carpool routes) ----------
# Expected context (multi-carpool):
#   selected_day (YYYY-MM-DD), members: [{user_id, member_key, display_name}], roles: {user_id: 'D/R/O'}
#   credits: {user_id: int}, suggestion_name (str|None), driver_is_explicit (bool),
#   can_edit (bool), no_carpool (bool)
# Also backwards compatible with legacy (members: [{key,name}], roles: {key: 'D/R/O'}, credits: {key:int})
TODAY_TMPL = r"""
{% extends "BASE_TMPL" %}{% block content %}
  <div class="grid">
    <div class="card">
      <!-- Carpool Context Header -->
      {% if session.get('carpool_name') %}
        <div style="margin-bottom: 14px; padding-bottom: 10px; border-bottom: 1px solid var(--border);">
          <div class="muted" style="font-size: .9rem;">Displaying data for</div>
          <div style="font-size: 1.1rem; font-weight: 600; color: var(--accent);">{{ session.get('carpool_name') }}</div>
        </div>
      {% endif %}

      <!-- NerdPool selector (only if multi mode) -->
      <!-- NerdPool selector moved to Navbar -->

      <!-- Tips lives UNDER the selector 
      <div class="card" style="background:#12141a; margin-bottom:10px;">
        <div class="form-row" style="justify-content:space-between; align-items:center;">
          <div>
            <div class="form-label">Tips</div>
            <div class="muted">• Switch NerdPools above • Admin can edit older than 7 days</div>
          </div>
          <a class="btn btn-secondary btn-sm" href="{{ url_for('historybp.history') }}">View History</a>
        </div>
      </div> -->


      <!-- Roles form -->
      <form method="post" class="grid" style="gap: 10px;" id="rolesForm">
        <input type="hidden" name="action" value="save_roles">
        <div class="form-row" style="align-items:end;">
          <div style="min-width:180px;">
            <label class="form-label">Select Date</label>
            <input class="form-control" type="date" name="day" id="dayInput" value="{{ selected_day }}" pattern=r"\d{4}-\d{2}-\d{2}">
          </div>
          <div>
            <button type="button" class="btn btn-secondary" onclick="var d = document.getElementById('dayInput').value; console.log('Go clicked, date:', d); window.location.href='/today?day=' + d;">Go</button>
          </div>
          <div>
            {% if can_edit %}
              <button class="btn btn-primary">Save</button>
            {% else %}
              <button class="btn" disabled title="Edits older than 7 days require admin">Save (locked)</button>
            {% endif %}
          </div>
        </div>

        <script>
          // Auto-reload when date changes
          document.getElementById('dayInput').addEventListener('change', function() {
            console.log('Date changed to:', this.value);
            window.location.href = '/today?day=' + this.value;
          });
        </script>
          {% if no_carpool %}
            <span class="badge" title="Fewer than two active">No NerdPool Today</span>
          {% endif %}
        </div>

        

        <div class="table-scroll">
          <table class="table">
            <thead>
              <tr><th>Member</th><th style="width:160px;">Status</th><th style="text-align:right;">Credits</th></tr>
            </thead>
            <tbody>
              {% for m in members %}
                {% set has_uid = ('user_id' in m) %}
                {% set field = ('u' ~ m['user_id']) if has_uid else m.get('key') %}
                {% set label = m.get('display_name') or m.get('name') or m.get('key') %}
                {% set key_for_roles = m['user_id'] if has_uid else m.get('key') %}
                {% set current = roles.get(key_for_roles, 'R') %}
                {% set credit_val = credits.get(key_for_roles, 0) %}
                <tr>
                  <td>{{ label }}</td>
                  <td>
                    <select class="form-select" name="{{ field }}" {{ 'disabled' if not can_edit else '' }}>
                      <option value="D" {{ 'selected' if current=='D' else '' }}>Driver</option>
                      <option value="R" {{ 'selected' if current=='R' else '' }}>Rider</option>
                      <option value="O" {{ 'selected' if current=='O' else '' }}>Off</option>
                    </select>
                  </td>
                  <td style="text-align:right;"><span class="muted">{{ credit_val }}</span></td>
                </tr>
              {% endfor %}
              {% if not members %}
                <tr><td colspan="3" class="muted">No active members in this NerdPool.</td></tr>
              {% endif %}
            </tbody>
          </table>
        </div>
        
            {% if suggestion_name %}
                <div class="callout {{ 'callout-success' if driver_is_explicit else 'callout-info' }}">
                <!-- <div class="title">{{ 'Driver set' if driver_is_explicit else 'Suggested driver' }}</div> -->
                <strong>{{ suggestion_name }}</strong> {{ 'is driving.' if driver_is_explicit else 'should drive.' }}
                </div>
            {% endif %}
        
      </form>
    </div>
  </div>
{% endblock %}
"""

# ---------- History (generic/dynamic table; many routes use inline templates, but we still provide this) ----------
# Expected context: rows=[{day_fmt:'Mon 2025-09-08', 'CA':'D','ER':'R','SJ':'O'}]
HISTORY_TMPL = r"""
{% extends "BASE_TMPL" %}{% block content %}
  <h3>History</h3>
  <div class="table-scroll">
    <table class="table">
      <thead><tr>
        {% if rows and rows[0].get('day_fmt') is not none %}
          <th>Date</th>
          {% for k, v in rows[0].items() if k not in ('day_fmt',) %}
            <th>{{ k }}</th>
          {% endfor %}
        {% else %}
          <th>Date</th><th>Member 1</th><th>Member 2</th><th>Member 3</th>
        {% endif %}
      </tr></thead>
      <tbody>
        {% for r in rows %}
          <tr>
            <td>{{ r['day_fmt'] }}</td>
            {% for k, v in r.items() if k not in ('day_fmt',) %}
              <td>{{ v or '' }}</td>
            {% endfor %}
          </tr>
        {% endfor %}
        {% if not rows %}
          <tr><td colspan="4" class="muted">No results</td></tr>
        {% endif %}
      </tbody>
    </table>
  </div>
{% endblock %}
"""

# ---------- Member stats (used by routes_history.member_stats) ----------
# Context: member_key, member_name, counts={'D': n, 'R': n, 'O': n}
STATS_TMPL = r"""
{% extends "BASE_TMPL" %}{% block content %}
  <h3>Stats — {{ member_name }} ({{ member_key }})</h3>
  <div class="grid grid-2">
    <div class="card">
      <table class="table">
        <thead><tr><th>Role</th><th>Count</th></tr></thead>
        <tbody>
          <tr><td>Driver</td><td>{{ counts.get('D', 0) }}</td></tr>
          <tr><td>Rider</td><td>{{ counts.get('R', 0) }}</td></tr>
          <tr><td>Off</td><td>{{ counts.get('O', 0) }}</td></tr>
          <tr><td><strong>Total</strong></td><td><strong>{{ counts.get('D',0)+counts.get('R',0)+counts.get('O',0) }}</strong></td></tr>
        </tbody>
      </table>
    </div>
    <div class="card">
      <div class="muted">Tip: switch carpools from the navbar to view other groups.</div>
    </div>
  </div>
{% endblock %}
"""
