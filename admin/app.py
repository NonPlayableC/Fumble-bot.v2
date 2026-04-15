import os
import json
from datetime import datetime
from functools import wraps
from flask import Flask, request, render_template, redirect, url_for, session, jsonify
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("ADMIN_SECRET_KEY", "change_this_secret_key_123")

# Supabase с Service Role Key (полный доступ)
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

# Basic Auth
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "password")

def check_auth(username, password):
    return username == ADMIN_USER and password == ADMIN_PASS

def authenticate():
    return response('Access denied', 401, {'WWW-Authenticate': 'Basic realm="Admin"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# Главная страница
@app.route('/')
@requires_auth
def dashboard():
    return render_template('dashboard.html')

# API для получения данных
@app.route('/api/users')
@requires_auth
def api_users():
    res = supabase.table('users').select('*').order('created_at', desc=True).limit(100).execute()
    return jsonify(res.data)

@app.route('/api/stats')
@requires_auth
def api_stats():
    users = supabase.table('users').select('*', count='exact').execute()
    fumbles = supabase.table('fumbles').select('*', count='exact').execute()
    return jsonify({
        'users': users.count,
        'fumbles': fumbles.count
    })

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))