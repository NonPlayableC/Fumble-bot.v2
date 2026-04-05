import os
import sqlite3
import logging
from flask import Flask, render_template_string, request, redirect, url_for, session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("ADMIN_SECRET_KEY", "fumbl_super_secret_key_123")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin_fumbl_2024")
PORT = int(os.getenv("PORT", 5000))

# Path to DB (ensure it matches main_v2.py)
DB_PATH = os.path.join(os.path.dirname(__file__), 'fumbl.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>FUMBL Admin Panel</title>
    <style>
        body { font-family: sans-serif; background: #121212; color: #e0e0e0; margin: 20px; }
        h1 { color: #ff5252; }
        .stats-card { background: #1e1e1e; padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #333; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #333; }
        th { background: #252525; color: #ff5252; }
        tr:hover { background: #2a2a2a; }
        .login-form { max-width: 300px; margin: 100px auto; background: #1e1e1e; padding: 30px; border-radius: 8px; }
        input { width: 100%; padding: 10px; margin: 10px 0; border-radius: 4px; border: 1px solid #333; background: #121212; color: white; box-sizing: border-box; }
        button { width: 100%; padding: 10px; background: #ff5252; border: none; color: white; border-radius: 4px; cursor: pointer; font-weight: bold; }
        button:hover { background: #ff1744; }
        .nav { margin-bottom: 20px; }
        .nav a { color: #ff5252; text-decoration: none; margin-right: 15px; font-weight: bold; }
    </style>
</head>
<body>
    {% if not logged_in %}
        <div class="login-form">
            <h2 style="text-align:center; color:#ff5252;">FUMBL LOGIN</h2>
            <form method="POST" action="/login">
                <input type="password" name="password" placeholder="Password" required>
                <button type="submit">ENTER THE VOID</button>
            </form>
            {% if error %}<p style="color:red; text-align:center;">{{ error }}</p>{% endif %}
        </div>
    {% else %}
        <div class="nav">
            <a href="/">DASHBOARD</a>
            <a href="/logout" style="color:#888;">LOGOUT</a>
        </div>
        <h1>🤡 FUMBL ADMIN PANEL</h1>
        
        <div class="stats-card">
            <h2>GLOBAL STATS</h2>
            <p>Total Users: <strong>{{ stats.total_users }}</strong></p>
            <p>Total Fumbles: <strong>{{ stats.total_fumbles }}</strong></p>
            <p>Active Subscriptions: <strong>{{ stats.total_subs }}</strong></p>
        </div>

        <div class="stats-card">
            <h2>RECENT USERS</h2>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Lang</th>
                        <th>Lvl</th>
                        <th>Wallet</th>
                        <th>Subs</th>
                    </tr>
                </thead>
                <tbody>
                    {% for user in recent_users %}
                    <tr>
                        <td>{{ user.user_id }}</td>
                        <td>{{ user.lang }}</td>
                        <td>{{ user.level }}</td>
                        <td>{{ user.wallet_address or 'None' }}</td>
                        <td>{{ '✅' if user.is_subscribed else '❌' }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    {% endif %}
</body>
</html>
"""

@app.route("/")
def index():
    if not session.get("logged_in"):
        return render_template_string(HTML_TEMPLATE, logged_in=False)
    
    conn = get_db_connection()
    stats = {}
    try:
        stats['total_users'] = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        stats['total_fumbles'] = conn.execute("SELECT COUNT(*) FROM fumbles").fetchone()[0]
        stats['total_subs'] = conn.execute("SELECT COUNT(*) FROM users WHERE is_subscribed = 1").fetchone()[0]
        recent_users = conn.execute("SELECT * FROM users ORDER BY last_seen DESC LIMIT 20").fetchall()
    except Exception as e:
        logger.error(f"DB Error: {e}")
        stats = {'total_users': 0, 'total_fumbles': 0, 'total_subs': 0}
        recent_users = []
    finally:
        conn.close()
    
    return render_template_string(HTML_TEMPLATE, logged_in=True, stats=stats, recent_users=recent_users)

@app.route("/login", methods=["POST"])
def login():
    if request.form.get("password") == ADMIN_PASSWORD:
        session["logged_in"] = True
        return redirect(url_for("index"))
    return render_template_string(HTML_TEMPLATE, logged_in=False, error="Wrong password, clown.")

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
