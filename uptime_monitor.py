#!/usr/bin/env python3
"""
Service Uptime Monitor – Full-featured version
----------------------------------------------
Features:
- SQLite persistence (history survives restarts)
- Email alerts on state changes
- HTTP, TCP, and SSL certificate checks
- Rolling uptime: 1h, 24h, 7d
- Teal Flask dashboard with auto-refresh
"""

import time
import threading
import datetime
import smtplib
import socket
import ssl
import sqlite3
import os
from email.mime.text import MIMEText

import requests
from flask import Flask, render_template_string, jsonify

# ===========================
#  CONFIGURATION (EDIT ME!)
# ===========================

# --- Services to monitor ---
# type: 'http', 'tcp', or 'ssl'
SERVICES = [
    {"name": "Google", "url": "https://www.google.com", "type": "http"},
    {"name": "GitHub API", "url": "https://api.github.com", "type": "http"},
    {"name": "Example", "url": "https://example.com", "type": "http"},
    # TCP example (uncomment and adjust IP/port):
    # {"name": "Local Router", "host": "192.168.1.1", "port": 80, "type": "tcp"},
    # SSL certificate expiry example:
    # {"name": "My SSL Cert", "host": "example.com", "port": 443, "type": "ssl"},
]

CHECK_INTERVAL = 60          # seconds between checks
DASHBOARD_REFRESH = 30       # seconds (client-side auto-refresh)
PORT = 5000

# --- Email alert settings (DISABLED BY DEFAULT FOR PUBLIC DEPLOYMENT) ---
# Email is OFF by default. To enable it, set EMAIL_ENABLED=true in your environment.
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "False").lower() == "true"

# These are only used if EMAIL_ENABLED is True
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT", "")

# ===========================
#  DATABASE SETUP (SQLite)
# ===========================

DB_NAME = "uptime.db"

def init_db():
    """Create the checks table if it doesn't exist."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS checks (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 service_name TEXT,
                 timestamp TEXT,
                 status INTEGER,   -- 1 = up, 0 = down
                 response_time REAL
                 )''')
    conn.commit()
    conn.close()

def save_check(name, is_up, elapsed_ms):
    """Insert a single check result into the database."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO checks (service_name, timestamp, status, response_time) VALUES (?, ?, ?, ?)",
              (name, datetime.datetime.now().isoformat(), 1 if is_up else 0, elapsed_ms))
    conn.commit()
    conn.close()

def get_history(name, limit=1440):
    """Retrieve the last 'limit' checks for a service."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT timestamp, status FROM checks WHERE service_name = ? ORDER BY id DESC LIMIT ?", (name, limit))
    rows = c.fetchall()
    conn.close()
    # Convert to list of (timestamp, bool) for compatibility
    return [(row[0], bool(row[1])) for row in rows]

def get_rolling_uptime(name, hours):
    """
    Calculate uptime percentage for a service over the last 'hours' hours.
    Returns 0.0 if no data exists.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT (CAST(SUM(status) AS FLOAT) / COUNT(*)) * 100
        FROM checks
        WHERE service_name = ? AND timestamp > datetime('now', ?)
    """, (name, f'-{hours} hours'))
    result = c.fetchone()[0]
    conn.close()
    return round(result, 1) if result is not None else 0.0

# ===========================
#  EMAIL ALERTS
# ===========================

def send_email_alert(service_name, is_up, response_time, details=""):
    """Send an email notification about a service state change."""
    if not EMAIL_ENABLED:
        return
    status_text = "UP" if is_up else "DOWN"
    subject = f"[Uptime Alert] {service_name} is {status_text}"
    body = f"""
Service: {service_name}
Status: {status_text}
Response Time: {response_time:.1f}ms
Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Details: {details}
    """
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECIPIENT

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        print(f"📧 Alert email sent for {service_name}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

# ===========================
#  CHECK FUNCTIONS (HTTP / TCP / SSL)
# ===========================

def check_http(svc):
    """Perform an HTTP/HTTPS check."""
    start = time.time()
    try:
        resp = requests.get(svc["url"], timeout=5)
        elapsed_ms = (time.time() - start) * 1000
        is_up = resp.status_code == 200
        details = f"Status Code: {resp.status_code}"
    except requests.RequestException as e:
        elapsed_ms = 0.0
        is_up = False
        details = f"Exception: {str(e)[:50]}"
    return is_up, elapsed_ms, details

def check_tcp(svc):
    """Perform a TCP port check."""
    start = time.time()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3)
            result = s.connect_ex((svc["host"], svc["port"]))
            elapsed_ms = (time.time() - start) * 1000
            is_up = (result == 0)
            details = f"Port {svc['port']} {'open' if is_up else 'closed/unreachable'}"
    except Exception as e:
        elapsed_ms = 0.0
        is_up = False
        details = f"Error: {str(e)[:50]}"
    return is_up, elapsed_ms, details

def check_ssl(svc):
    """Check SSL certificate expiry (alert if < 7 days remaining)."""
    start = time.time()
    try:
        context = ssl.create_default_context()
        with socket.create_connection((svc["host"], svc["port"]), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=svc["host"]) as ssock:
                cert = ssock.getpeercert()
                expiry_str = cert['notAfter']
                expiry = datetime.datetime.strptime(expiry_str, '%b %d %H:%M:%S %Y %Z')
                days_left = (expiry - datetime.datetime.now()).days
                elapsed_ms = (time.time() - start) * 1000
                is_up = days_left > 7   # Treat as "up" if more than 7 days left
                details = f"Expires in {days_left} days"
    except Exception as e:
        elapsed_ms = 0.0
        is_up = False
        details = f"SSL Error: {str(e)[:50]}"
    return is_up, elapsed_ms, details

def perform_check(svc):
    """Route to the appropriate check function based on service type."""
    check_type = svc.get("type", "http")
    if check_type == "http":
        return check_http(svc)
    elif check_type == "tcp":
        return check_tcp(svc)
    elif check_type == "ssl":
        return check_ssl(svc)
    else:
        return False, 0.0, f"Unknown type: {check_type}"

# ===========================
#  BACKGROUND MONITORING THREAD
# ===========================

# Keep track of the last known state for alerting (in memory)
last_known_state = {}

def monitor_loop():
    """Background thread: checks all services every CHECK_INTERVAL seconds."""
    while True:
        for svc in SERVICES:
            name = svc['name']
            is_up, elapsed_ms, details = perform_check(svc)

            # Save the result to the database
            save_check(name, is_up, elapsed_ms)

            # Alert on state change (only if we have a previous state)
            previous = last_known_state.get(name)
            if previous is not None and previous != is_up:
                send_email_alert(name, is_up, elapsed_ms, details)
            # Update the last known state
            last_known_state[name] = is_up

            # Optional: print a heartbeat to the console
            status_str = "✅ UP" if is_up else "❌ DOWN"
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {name}: {status_str} ({elapsed_ms:.1f}ms)")

        time.sleep(CHECK_INTERVAL)

# ===========================
#  FLASK DASHBOARD
# ===========================

app = Flask(__name__)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Service Uptime Monitor</title>
    <!-- FAVICON: Now using the 📡 emoji directly -->
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📡</text></svg>">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #e0f2f1;
            padding: 2rem;
            color: #004d40;
        }
        h1 {
            text-align: center;
            color: #00695c;
            border-bottom: 3px solid #00897b;
            padding-bottom: 0.5rem;
            margin-bottom: 0.5rem;
        }
        .card-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
            max-width: 1400px;
            margin: 8rem auto 0 auto;  /* MUCH MORE SPACE from the header */
        }
        .card {
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            border-left: 8px solid #00897b;
            transition: transform 0.2s;
        }
        .card:hover { transform: translateY(-5px); }
        .card h2 {
            font-size: 1.5rem;
            margin-bottom: 0.75rem;
            color: #00695c;
        }
        .status-indicator {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 1.2rem;
            margin: 0.5rem 0;
        }
        .status-badge {
            display: inline-block;
            padding: 0.2rem 0.8rem;
            border-radius: 20px;
            font-weight: bold;
            font-size: 0.9rem;
        }
        .up { background: #a5d6a7; color: #1b5e20; }
        .down { background: #ef9a9a; color: #b71c1c; }
        .info-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.3rem 1rem;
            margin-top: 1rem;
            font-size: 0.9rem;
        }
        .info-grid .label { color: #00796b; font-weight: 500; }
        .info-grid .value { text-align: right; font-family: monospace; }
        .footer {
            text-align: center;
            margin-top: 2rem;
            color: #00796b;
            font-size: 0.9rem;
        }
        .refresh-note {
            background: #b2dfdb;
            padding: 0.4rem 1rem;
            border-radius: 30px;
            display: inline-block;
            margin-top: 0.5rem;
            font-weight: 500;
        }
        .uptime-bar {
            background: #e0e0e0;
            border-radius: 10px;
            height: 8px;
            margin-top: 4px;
            overflow: hidden;
        }
        .uptime-fill {
            height: 100%;
            background: #00897b;
            border-radius: 10px;
            transition: width 0.5s;
        }
    </style>
</head>
<body>
    <h1>📡 Service Uptime Monitor</h1>
    <div class="card-container">
        {% for svc in services %}
        <div class="card">
            <h2>{{ svc.name }}</h2>
            <div class="status-indicator">
                <span class="status-badge {{ 'up' if svc.status else 'down' }}">
                    {{ '✔ Up' if svc.status else '✕ Down' }}
                </span>
                <span style="font-size:0.9rem; color:#555;">
                    ({{ svc.uptime_24h }}% over 24h)
                </span>
            </div>
            <div class="info-grid">
                <span class="label">Last Check</span>
                <span class="value">{{ svc.last_check }}</span>
                <span class="label">Response</span>
                <span class="value">{{ svc.response_time or 'N/A' }} ms</span>
                <span class="label">Total Checks</span>
                <span class="value">{{ svc.total_checks }}</span>
                <span class="label">Uptime (1h)</span>
                <span class="value">{{ svc.uptime_1h }}%</span>
                <span class="label">Uptime (24h)</span>
                <span class="value">{{ svc.uptime_24h }}%</span>
                <span class="label">Uptime (7d)</span>
                <span class="value">{{ svc.uptime_7d }}%</span>
            </div>
            <!-- Visual bars for quick scanning -->
            <div style="margin-top: 10px;">
                <div style="display:flex; justify-content:space-between; font-size:0.7rem; color:#555;">
                    <span>1h: {{ svc.uptime_1h }}%</span>
                    <span>24h: {{ svc.uptime_24h }}%</span>
                    <span>7d: {{ svc.uptime_7d }}%</span>
                </div>
                <div style="display:flex; gap:4px; margin-top:2px;">
                    <div class="uptime-bar" style="flex:1;"><div class="uptime-fill" style="width:{{ svc.uptime_1h }}%;"></div></div>
                    <div class="uptime-bar" style="flex:1;"><div class="uptime-fill" style="width:{{ svc.uptime_24h }}%;"></div></div>
                    <div class="uptime-bar" style="flex:1;"><div class="uptime-fill" style="width:{{ svc.uptime_7d }}%;"></div></div>
                </div>
            </div>
        </div>
        {% endfor %}
    </div>
    <div class="footer">
        <!-- COUNTDOWN TIMER -->
        <span class="refresh-note">↻ Refreshing in <span id="countdown-timer">{{ refresh_seconds }}</span>s</span>
        <br><br>
        <span style="font-size:0.8rem;">Built with Python, Flask, SQLite • Alerts via Email</span>
    </div>

    <!-- JAVASCRIPT FOR COUNTDOWN -->
    <script>
        let seconds = {{ refresh_seconds }};
        const timerElement = document.getElementById('countdown-timer');

        function updateCountdown() {
            timerElement.textContent = seconds;
            if (seconds === 0) {
                location.reload();
            } else {
                seconds--;
            }
        }

        updateCountdown();
        setInterval(updateCountdown, 1000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """Render the dashboard with live data."""
    services_data = []
    for svc in SERVICES:
        name = svc['name']
        history = get_history(name, limit=1440)  # last 1440 checks (1 day at 1/min)
        total = len(history)
        if total > 0:
            up_count = sum(1 for _, up in history if up)
            # The last check is the most recent (since we ORDER BY id DESC)
            last_status = history[0][1] if history else False
            last_check_time = history[0][0] if history else "Never"
        else:
            last_status = False
            last_check_time = "Never"

        # Get latest response time from the DB (most recent check)
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT response_time FROM checks WHERE service_name = ? ORDER BY id DESC LIMIT 1", (name,))
        row = c.fetchone()
        conn.close()
        latest_response = round(row[0], 1) if row and row[0] is not None else None

        services_data.append({
            'name': name,
            'status': last_status,
            'last_check': last_check_time,
            'response_time': latest_response,
            'total_checks': total,
            'uptime_1h': get_rolling_uptime(name, 1),
            'uptime_24h': get_rolling_uptime(name, 24),
            'uptime_7d': get_rolling_uptime(name, 168),
        })

    return render_template_string(
        HTML_TEMPLATE,
        services=services_data,
        refresh_seconds=DASHBOARD_REFRESH
    )

@app.route('/api/status')
def api_status():
    """JSON endpoint for programmatic access."""
    # Return all raw data from DB (last 10 checks per service for brevity)
    result = {}
    for svc in SERVICES:
        name = svc['name']
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT timestamp, status, response_time FROM checks WHERE service_name = ? ORDER BY id DESC LIMIT 10", (name,))
        rows = c.fetchall()
        conn.close()
        result[name] = [{"timestamp": r[0], "status": bool(r[1]), "response_time": r[2]} for r in rows]
    return jsonify(result)

# ===========================
#  MAIN ENTRY POINT
# ===========================

if __name__ == '__main__':
    # Initialise the database
    init_db()
    print(f"📂 Database: {DB_NAME}")

    # Start the background monitoring thread
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()
    print(f"🚀 Uptime Monitor started. Dashboard at http://localhost:{PORT}")
    print(f"📋 Monitoring {len(SERVICES)} services every {CHECK_INTERVAL}s")
    if EMAIL_ENABLED:
        print(f"✉️  Email alerts enabled (to {EMAIL_RECIPIENT})")
    else:
        print("🔕 Email alerts disabled")

    # Run Flask (disable debug/reloader to avoid duplicate threads)
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
