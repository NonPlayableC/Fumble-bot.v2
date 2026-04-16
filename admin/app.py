import os
import json
from datetime import datetime
from functools import wraps
from flask import Flask, request, render_template, redirect, url_for, session, jsonify, Response
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("ADMIN_SECRET_KEY", "change_this_secret_key_123")

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "password")

def check_auth(username, password):
    return username == ADMIN_USER and password == ADMIN_PASS

def authenticate():
    return Response('Access denied', 401, {'WWW-Authenticate': 'Basic realm="Admin"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# Главная
@app.route('/')
@requires_auth
def dashboard():
    return render_template('dashboard.html')

@app.route('/logout')
def logout():
    return authenticate()

# Статистика
@app.route('/api/stats')
@requires_auth
def api_stats():
    users = supabase.table('users').select('*', count='exact').execute()
    fumbles = supabase.table('fumbles').select('*', count='exact').execute()
    signals = supabase.table('signal_history').select('*', count='exact').execute()
    subscribers = supabase.table('users').select('*', count='exact').eq('subscribed', True).execute()
    return jsonify({
        'users': users.count,
        'fumbles': fumbles.count,
        'signals': signals.count,
        'subscribers': subscribers.count
    })

@app.route('/api/recent-users')
@requires_auth
def api_recent_users():
    res = supabase.table('users').select('user_id, username, first_name, language, created_at').order('created_at', desc=True).limit(5).execute()
    return jsonify(res.data)

# Пользователи
@app.route('/users')
@requires_auth
def users_page():
    return render_template('users.html')

@app.route('/api/users')
@requires_auth
def api_users():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    offset = (page - 1) * per_page
    res = supabase.table('users').select('*, user_stats(*)').order('created_at', desc=True).range(offset, offset + per_page - 1).execute()
    count_res = supabase.table('users').select('*', count='exact').execute()
    return jsonify({
        'users': res.data,
        'total': count_res.count or 0,
        'page': page,
        'per_page': per_page
    })

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@requires_auth
def api_update_user(user_id):
    data = request.json
    updates = {}
    if 'blocked' in data: updates['blocked'] = data['blocked']
    if 'streak_days' in data: updates['streak_days'] = data['streak_days']
    if updates: supabase.table('users').update(updates).eq('user_id', user_id).execute()
    if 'total_score' in data: supabase.table('user_stats').update({'total_score': data['total_score']}).eq('user_id', user_id).execute()
    if 'balance' in data: supabase.table('user_balances').upsert({'user_id': user_id, 'amount': data['balance']}).execute()
    return jsonify({'success': True})

@app.route('/api/users/search')
@requires_auth
def api_search_users():
    query = request.args.get('q', '')
    res = supabase.table('users').select('*, user_stats(*)').or_(f"username.ilike.%{query}%,first_name.ilike.%{query}%,user_id.eq.{query if query.isdigit() else 0}").limit(50).execute()
    return jsonify(res.data)

# Мемы
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

# Стикеры
@app.route('/stickers')
@requires_auth
def stickers_page():
    return render_template('stickers.html')

@app.route('/api/stickers')
@requires_auth
def api_stickers():
    res = supabase.table('stickers').select('*').order('id', desc=True).execute()
    return jsonify(res.data)

@app.route('/api/stickers', methods=['POST'])
@requires_auth
def api_add_sticker():
    data = request.json
    supabase.table('stickers').insert({'file_id': data['file_id'], 'pack': data['pack']}).execute()
    return jsonify({'success': True})

@app.route('/api/stickers/<int:sticker_id>', methods=['DELETE'])
@requires_auth
def api_delete_sticker(sticker_id):
    supabase.table('stickers').delete().eq('id', sticker_id).execute()
    return jsonify({'success': True})

# Квесты
@app.route('/quests')
@requires_auth
def quests_page():
    return render_template('quests.html')

@app.route('/api/quests')
@requires_auth
def api_quests():
    res = supabase.table('quests').select('*').order('id', desc=True).execute()
    return jsonify(res.data)

@app.route('/api/quests', methods=['POST'])
@requires_auth
def api_create_quest():
    supabase.table('quests').insert(request.json).execute()
    return jsonify({'success': True})

@app.route('/api/quests/<int:quest_id>', methods=['PUT'])
@requires_auth
def api_update_quest(quest_id):
    supabase.table('quests').update(request.json).eq('id', quest_id).execute()
    return jsonify({'success': True})

@app.route('/api/quests/<int:quest_id>', methods=['DELETE'])
@requires_auth
def api_delete_quest(quest_id):
    supabase.table('quests').delete().eq('id', quest_id).execute()
    return jsonify({'success': True})

# Сигналы
@app.route('/signals')
@requires_auth
def signals_page():
    return render_template('signals.html')

@app.route('/api/signals')
@requires_auth
def api_signals():
    res = supabase.table('signals').select('*').order('id', desc=True).execute()
    return jsonify(res.data)

@app.route('/api/signals', methods=['POST'])
@requires_auth
def api_create_signal():
    supabase.table('signals').insert(request.json).execute()
    return jsonify({'success': True})

@app.route('/api/signals/<int:signal_id>', methods=['PUT'])
@requires_auth
def api_update_signal(signal_id):
    supabase.table('signals').update(request.json).eq('id', signal_id).execute()
    return jsonify({'success': True})

@app.route('/api/signals/<int:signal_id>', methods=['DELETE'])
@requires_auth
def api_delete_signal(signal_id):
    supabase.table('signals').delete().eq('id', signal_id).execute()
    return jsonify({'success': True})

# Вопросы фамбла
@app.route('/fumble')
@requires_auth
def fumble_page():
    return render_template('fumble_questions.html')

@app.route('/api/fumble-questions')
@requires_auth
def api_fumble_questions():
    res = supabase.table('fumble_questions').select('*, fumble_options(*)').order('id', desc=True).execute()
    return jsonify(res.data)

@app.route('/api/fumble-questions', methods=['POST'])
@requires_auth
def api_create_fumble_question():
    data = request.json
    options = data.pop('options', [])
    q_res = supabase.table('fumble_questions').insert(data).execute()
    question_id = q_res.data[0]['id']
    for opt in options:
        opt['question_id'] = question_id
        supabase.table('fumble_options').insert(opt).execute()
    return jsonify({'success': True})

@app.route('/api/fumble-questions/<int:q_id>', methods=['PUT'])
@requires_auth
def api_update_fumble_question(q_id):
    data = request.json
    options = data.pop('options', [])
    supabase.table('fumble_questions').update(data).eq('id', q_id).execute()
    supabase.table('fumble_options').delete().eq('question_id', q_id).execute()
    for opt in options:
        opt['question_id'] = q_id
        supabase.table('fumble_options').insert(opt).execute()
    return jsonify({'success': True})

@app.route('/api/fumble-questions/<int:q_id>', methods=['DELETE'])
@requires_auth
def api_delete_fumble_question(q_id):
    supabase.table('fumble_options').delete().eq('question_id', q_id).execute()
    supabase.table('fumble_questions').delete().eq('id', q_id).execute()
    return jsonify({'success': True})

# Достижения
@app.route('/achievements')
@requires_auth
def achievements_page():
    return render_template('achievements.html')

@app.route('/api/achievements-list')
@requires_auth
def api_achievements_list():
    res = supabase.table('achievements_list').select('*').order('achievement_key').execute()
    return jsonify(res.data)

@app.route('/api/achievements-list', methods=['POST'])
@requires_auth
def api_create_achievement():
    supabase.table('achievements_list').insert(request.json).execute()
    return jsonify({'success': True})

@app.route('/api/achievements-list/<key>', methods=['PUT'])
@requires_auth
def api_update_achievement(key):
    supabase.table('achievements_list').update(request.json).eq('achievement_key', key).execute()
    return jsonify({'success': True})

@app.route('/api/achievements-list/<key>', methods=['DELETE'])
@requires_auth
def api_delete_achievement(key):
    supabase.table('achievements_list').delete().eq('achievement_key', key).execute()
    return jsonify({'success': True})

# Подписчики
@app.route('/subscribers')
@requires_auth
def subscribers_page():
    return render_template('subscribers.html')

@app.route('/api/subscribers')
@requires_auth
def api_subscribers():
    res = supabase.table('users').select('user_id, username, first_name, language, subscription_date').eq('subscribed', True).execute()
    return jsonify(res.data)

@app.route('/api/broadcast', methods=['POST'])
@requires_auth
def api_broadcast():
    data = request.json
    message = data['message']
    lang = data.get('lang')
    query = supabase.table('users').select('user_id').eq('subscribed', True)
    if lang: query = query.eq('language', lang)
    res = query.execute()
    return jsonify({'success': True, 'count': len(res.data)})

# Логи ошибок
@app.route('/logs')
@requires_auth
def logs_page():
    return render_template('logs.html')

@app.route('/api/error-logs')
@requires_auth
def api_error_logs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    offset = (page - 1) * per_page
    res = supabase.table('error_logs').select('*').order('created_at', desc=True).range(offset, offset + per_page - 1).execute()
    count_res = supabase.table('error_logs').select('*', count='exact').execute()
    return jsonify({
        'logs': res.data,
        'total': count_res.count or 0,
        'page': page,
        'per_page': per_page
    })

@app.route('/api/error-logs', methods=['DELETE'])
@requires_auth
def api_clear_error_logs():
    supabase.table('error_logs').delete().neq('id', 0).execute()
    return jsonify({'success': True})

# Кэш и бэкап
@app.route('/api/clear-cache', methods=['POST'])
@requires_auth
def api_clear_cache():
    supabase.table('system').upsert({'key': 'cache_version', 'value': datetime.now().isoformat()}).execute()
    return jsonify({'success': True})

@app.route('/api/export')
@requires_auth
def api_export():
    tables = ['memes', 'stickers', 'quests', 'signals', 'fumble_questions', 'fumble_options', 'achievements_list']
    export_data = {}
    for table in tables:
        res = supabase.table(table).select('*').execute()
        export_data[table] = res.data
    return jsonify(export_data)

@app.route('/api/import', methods=['POST'])
@requires_auth
def api_import():
    data = request.json
    for table, rows in data.items():
        if rows:
            supabase.table(table).delete().neq('id', 0).execute()
            supabase.table(table).insert(rows).execute()
    return jsonify({'success': True})

@app.route('/translations')
@requires_auth
def translations_page():
    return render_template('translations.html')

@app.route('/api/translations')
@requires_auth
def api_translations():
    lang = request.args.get('lang', 'ru')
    res = supabase.table('translations').select('*').eq('lang', lang).order('key').execute()
    return jsonify(res.data)

@app.route('/api/translations', methods=['POST'])
@requires_auth
def api_save_translation():
    data = request.json
    supabase.table('translations').upsert({
        'lang': data['lang'],
        'key': data['key'],
        'value': data['value'],
        'updated_at': datetime.now().isoformat()
    }).execute()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))