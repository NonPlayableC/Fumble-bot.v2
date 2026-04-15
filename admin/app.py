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

# Страница пользователей
@app.route('/users')
@requires_auth
def users_page():
    return render_template('users.html')

# API: получить всех пользователей
@app.route('/api/users')
@requires_auth
def api_users():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    offset = (page - 1) * per_page
    
    res = supabase.table('users').select('*, user_stats(*)').order('created_at', desc=True).range(offset, offset + per_page - 1).execute()
    
    count_res = supabase.table('users').select('*', count='exact').execute()
    total = count_res.count if count_res.count else 0
    
    return jsonify({
        'users': res.data,
        'total': total,
        'page': page,
        'per_page': per_page
    })

# API: обновить пользователя
@app.route('/api/users/<int:user_id>', methods=['PUT'])
@requires_auth
def api_update_user(user_id):
    data = request.json
    
    updates = {}
    if 'blocked' in data:
        updates['blocked'] = data['blocked']
    if 'streak_days' in data:
        updates['streak_days'] = data['streak_days']
    
    if updates:
        supabase.table('users').update(updates).eq('user_id', user_id).execute()
    
    # Обновить очки фамбла
    if 'total_score' in data:
        supabase.table('user_stats').update({'total_score': data['total_score']}).eq('user_id', user_id).execute()
    
    # Обновить баланс BINTY
    if 'balance' in data:
        supabase.table('user_balances').upsert({'user_id': user_id, 'amount': data['balance']}).execute()
    
    return jsonify({'success': True})

# API: поиск пользователей
@app.route('/api/users/search')
@requires_auth
def api_search_users():
    query = request.args.get('q', '')
    res = supabase.table('users').select('*, user_stats(*)').or_(f"username.ilike.%{query}%,first_name.ilike.%{query}%,user_id.eq.{query if query.isdigit() else 0}").limit(50).execute()
    return jsonify(res.data)
    
@app.route('/memes')
@requires_auth
def memes_page():
    return render_template('memes.html')

@app.route('/api/memes')
@requires_auth
def api_memes():
    res = supabase.table('memes').select('*').order('id', desc=True).execute()
    return jsonify(res.data)

@app.route('/api/memes', methods=['POST'])
@requires_auth
def api_add_meme():
    data = request.json
    supabase.table('memes').insert({'url': data['url']}).execute()
    return jsonify({'success': True})

@app.route('/api/memes/<int:meme_id>', methods=['DELETE'])
@requires_auth
def api_delete_meme(meme_id):
    supabase.table('memes').delete().eq('id', meme_id).execute()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))