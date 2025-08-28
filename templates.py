# templates.py

BASE_TMPL = """
<!doctype html>
<html lang="en" data-bs-theme="light">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CESpool</title>

  <!-- Bootstrap CSS -->
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">

  <style>
    :root { color-scheme: light dark; }
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, Noto Sans; margin: 1rem; }
    main { max-width: 980px; margin: 0 auto; }
    .grid { display: grid; grid-template-columns: repeat(3, minmax(160px,1fr)); gap: .75rem; }
    @media (max-width: 720px) { .grid { grid-template-columns: 1fr; } }
    .card { border: 1px solid var(--bs-border-color); border-radius: .5rem; padding: .75rem; background: var(--bs-body-bg); }
    .table-scroll { max-height: 70vh; overflow: auto; border:1px solid var(--bs-border-color); border-radius:.5rem; }
    .table-sticky thead th { position: sticky; top: 0; z-index: 2; background: var(--bs-body-bg); }
    .theme-btn { border:none; background:none; padding:.25rem .5rem; font-size:1.2rem }
    .muted { opacity:.8 }
  </style>

  <script>
    // Set theme early to avoid flash
    (function() {
      const saved = localStorage.getItem('theme');
      const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      const theme = saved || (prefersDark ? 'dark' : 'light');
      document.documentElement.setAttribute('data-bs-theme', theme);
    })();
  </script>
</head>
<body>
<nav class="navbar navbar-expand-lg bg-body-tertiary border-bottom">
  <div class="container-fluid">
    <a class="navbar-brand" href="{{ url_for('todaybp.today') }}">CESpool</a>
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navmenu"
            aria-controls="navmenu" aria-expanded="false" aria-label="Toggle navigation">
      <span class="navbar-toggler-icon"></span>
    </button>

    <div class="collapse navbar-collapse justify-content-end" id="navmenu">
      <ul class="navbar-nav">
        <li class="nav-item"><a class="nav-link" href="{{ url_for('todaybp.today') }}">Today</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('historybp.history') }}">History</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('authbp.account') }}">Account</a></li>
        {% if current_user.is_authenticated and current_user.is_admin %}
          <li class="nav-item"><a class="nav-link" href="{{ url_for('adminbp.admin_users') }}">Users</a></li>
          <li class="nav-item"><a class="nav-link" href="{{ url_for('adminbp.admin_diag') }}">Diag</a></li>
          <li class="nav-item"><a class="nav-link" href="{{ url_for('adminbp.admin_audit') }}">Audit</a></li>
        {% endif %}
        <li class="nav-item"><a class="nav-link" href="{{ url_for('authbp.logout') }}">Logout</a></li>
      </ul>
      <button id="themeToggle" class="theme-btn ms-2" title="Toggle dark mode">🌓</button>
    </div>
  </div>
</nav>

<main>
  {% block content %}{% endblock %}

  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
      {% for category, message in messages %}
        <div class="alert {{ 'alert-danger' if category=='error' else 'alert-success' }} mt-3" role="alert">{{ message }}</div>
      {% endfor %}
    {% endif %}
  {% endwith %}
</main>

<script>
  (function(){
    const btn = document.getElementById('themeToggle');
    const nav = document.querySelector('nav.navbar');

    function getTheme(){ return document.documentElement.getAttribute('data-bs-theme') || 'light'; }
    function setTheme(t){
      document.documentElement.setAttribute('data-bs-theme', t);
      localStorage.setItem('theme', t);
      applyNavTheme();
    }
    function applyNavTheme(){
      const t = getTheme();
      // Ensure Bootstrap knows which icon palette to use
      nav.classList.toggle('navbar-dark', t === 'dark');
      nav.classList.toggle('navbar-light', t !== 'dark');
    }

    // initial apply + on click
    applyNavTheme();
    btn && btn.addEventListener('click', function(){
      const next = getTheme()==='dark' ? 'light' : 'dark';
      setTheme(next);
    });
  })();
</script>

<!-- Bootstrap JS (bundle includes Popper) -->
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""


LOGIN_TMPL = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Login</title>
  <style>body{font-family:system-ui,sans-serif;margin:2rem;max-width:420px}</style>
</head>
<body>
  <h3>Login</h3>
  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
      {% for category, message in messages %}
        <div class="{{ category }}">{{ message }}</div>
      {% endfor %}
    {% endif %}
  {% endwith %}
  <form method="post">
    <label>Username<br><input name="username" required></label><br><br>
    <label>Password<br><input name="password" type="password" required></label><br><br>
    <label><input type="checkbox" name="remember"> Remember me</label>
    <button type="submit">Let me in</button>
  </form>
</body>
</html>
"""

# ✅ keep your existing TODAY_TMPL
TODAY_TMPL = """
{% extends "BASE_TMPL" %}{% block content %}
  <div class="mt-3"></div>  {# <-- spacing between navbar and form #}



  <form method="post" class="card">
    <div class="mb-2">
      <input type="date" name="day" value="{{ selected_day }}" onchange="window.location='{{ url_for('todaybp.today') }}?day='+this.value"/>
    </div>
    <div class="grid">
      {% for m in members %}
      <div>
        <div>
          <strong>{{ m['name'] }}</strong>
          <span class="muted">({{ credits.get(m['key'], 0) }} credits)</span>
        </div>
        <select name="{{ m['key'] }}">
          <option value="D" {% if roles[m['key']]=='D' %}selected{% endif %}>Driver</option>
          <option value="R" {% if roles[m['key']]=='R' %}selected{% endif %}>Rider</option>
          <option value="O" {% if roles[m['key']]=='O' %}selected{% endif %}>Off</option>
        </select>
      </div>
      {% endfor %}
    </div>
    <br>
    {% if can_edit %}
      <button type="submit" class="btn btn-primary">Save</button>
    {% else %}
      <button type="button" class="btn btn-secondary" disabled>Editing locked (admin only)</button>
    {% endif %}
  </form>

  {# Suggestion message box below the form #}
  {% if no_carpool %}
    <div class="alert alert-warning mt-3"><strong>No Carpool Today</strong></div>
  {% elif suggestion_name %}
    <div class="alert alert-info mt-3">
      {{ suggestion_name }} {{ 'is driving today' if driver_is_explicit else 'should drive' }}
    </div>
  {% endif %}

{% endblock %}
"""



HISTORY_TMPL = """
{% extends "BASE_TMPL" %}{% block content %}
  <h3>History</h3>
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
      </tbody>
    </table>
  </div>
{% endblock %}
"""

STATS_TMPL = """
{% extends "BASE_TMPL" %}{% block content %}
  <h3>{{ member_name }} — Stats</h3>
  <ul>
    <li>Drives: {{ counts.get('D',0) }}</li>
    <li>Rides: {{ counts.get('R',0) }}</li>
    <li>Off: {{ counts.get('O',0) }}</li>
  </ul>
{% endblock %}
"""
