import os
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from supabase import create_client, Client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("ADMIN_SECRET_KEY", "binty_super_secret_key_2026")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "binty_admin_2026")
PORT = int(os.getenv("ADMIN_PORT", 5000))

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = None

if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Language translations
TEXTS = {
    "en": {
        "title": "🤡 BINTY ADMIN PANEL",
        "login_title": "BINTY LOGIN",
        "password": "Password",
        "enter": "ENTER THE VOID",
        "wrong_password": "Wrong password, clown.",
        "dashboard": "DASHBOARD",
        "users": "USERS",
        "fumbles": "FUMBLES",
        "broadcast": "BROADCAST",
        "settings": "SETTINGS",
        "logout": "LOGOUT",
        "total_users": "Total Users",
        "total_fumbles": "Total Fumbles",
        "active_subs": "Active Subscriptions",
        "avg_score": "Avg Fumble Score",
        "dau": "DAU (24h)",
        "mau": "MAU (30d)",
        "recent_users": "Recent Users",
        "top_losers": "Top Losers",
        "id": "ID",
        "username": "Username",
        "language": "Lang",
        "level": "Lvl",
        "wallet": "Wallet",
        "subscribed": "Sub",
        "fumbles_count": "Fumbles",
        "score": "Score",
        "date": "Date",
        "actions": "Actions",
        "search": "Search",
        "search_placeholder": "Enter user ID or username",
        "broadcast_title": "Send Broadcast",
        "broadcast_text": "Message text",
        "broadcast_photo": "Photo URL (optional)",
        "broadcast_target": "Target",
        "all_users": "All users",
        "subscribers_only": "Subscribers only",
        "send": "Send Broadcast",
        "sent": "Broadcast sent!",
        "settings_title": "Settings",
        "memes_management": "Memes Management",
        "stickers_management": "Stickers Management",
        "achievements_management": "Achievements",
        "quests_management": "Quests",
        "add": "Add",
        "delete": "Delete",
        "save": "Save",
        "language_label": "Language",
        "view": "View",
        "block": "Block",
        "unblock": "Unblock",
        "make_admin": "Make Admin",
        "user_details": "User Details",
        "stats": "Statistics",
        "achievements": "Achievements",
        "quests": "Quests",
        "referrals": "Referrals",
        "no_data": "No data available",
        "loading": "Loading...",
    },
    "ru": {
        "title": "🤡 ПАНЕЛЬ АДМИНИСТРАТОРА BINTY",
        "login_title": "ВХОД BINTY",
        "password": "Пароль",
        "enter": "ВОЙТИ В БЕЗДНУ",
        "wrong_password": "Неверный пароль, клоун.",
        "dashboard": "ДАШБОРД",
        "users": "ПОЛЬЗОВАТЕЛИ",
        "fumbles": "ФАМБЛЫ",
        "broadcast": "РАССЫЛКА",
        "settings": "НАСТРОЙКИ",
        "logout": "ВЫХОД",
        "total_users": "Всего пользователей",
        "total_fumbles": "Всего фамблов",
        "active_subs": "Активных подписок",
        "avg_score": "Средний балл фамбла",
        "dau": "DAU (24ч)",
        "mau": "MAU (30д)",
        "recent_users": "Последние пользователи",
        "top_losers": "Топ лузеров",
        "id": "ID",
        "username": "Имя",
        "language": "Язык",
        "level": "Ур.",
        "wallet": "Кошелёк",
        "subscribed": "Подп.",
        "fumbles_count": "Фамблы",
        "score": "Счёт",
        "date": "Дата",
        "actions": "Действия",
        "search": "Поиск",
        "search_placeholder": "Введите ID или имя пользователя",
        "broadcast_title": "Отправить рассылку",
        "broadcast_text": "Текст сообщения",
        "broadcast_photo": "URL фото (необязательно)",
        "broadcast_target": "Получатели",
        "all_users": "Все пользователи",
        "subscribers_only": "Только подписчики",
        "send": "Отправить",
        "sent": "Рассылка отправлена!",
        "settings_title": "Настройки",
        "memes_management": "Управление мемами",
        "stickers_management": "Управление стикерами",
        "achievements_management": "Достижения",
        "quests_management": "Квесты",
        "add": "Добавить",
        "delete": "Удалить",
        "save": "Сохранить",
        "language_label": "Язык",
        "view": "Смотреть",
        "block": "Заблокировать",
        "unblock": "Разблокировать",
        "make_admin": "Сделать админом",
        "user_details": "Детали пользователя",
        "stats": "Статистика",
        "achievements": "Достижения",
        "quests": "Квесты",
        "referrals": "Рефералы",
        "no_data": "Нет данных",
        "loading": "Загрузка...",
    }
}

# HTML Template with dual language support
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>BINTY Admin</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', 'Arial', sans-serif; 
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0; 
            min-height: 100vh;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        h1, h2, h3 { color: #ff6b6b; margin-bottom: 15px; }
        h1 { font-size: 2rem; border-bottom: 2px solid #ff6b6b; padding-bottom: 10px; }
        h2 { font-size: 1.4rem; margin-top: 10px; }
        
        /* Navigation */
        .nav { 
            display: flex; 
            gap: 5px; 
            margin-bottom: 25px; 
            background: #0f3460; 
            padding: 10px 15px; 
            border-radius: 12px;
            flex-wrap: wrap;
        }
        .nav a { 
            color: #e0e0e0; 
            text-decoration: none; 
            padding: 10px 20px; 
            border-radius: 8px;
            font-weight: 500;
            transition: all 0.2s;
        }
        .nav a:hover { background: #e94560; color: white; }
        .nav a.active { background: #e94560; color: white; }
        .nav-right { margin-left: auto; display: flex; gap: 10px; }
        
        /* Cards */
        .stats-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); 
            gap: 20px; 
            margin-bottom: 25px; 
        }
        .stat-card { 
            background: #0f3460; 
            padding: 22px 18px; 
            border-radius: 16px; 
            border: 1px solid #e94560;
            box-shadow: 0 4px 15px rgba(233, 69, 96, 0.2);
            text-align: center;
        }
        .stat-card h3 { 
            color: #888; 
            font-size: 0.9rem; 
            text-transform: uppercase; 
            letter-spacing: 1px;
            margin-bottom: 10px;
        }
        .stat-card .value { 
            font-size: 2.8rem; 
            font-weight: bold; 
            color: #ff6b6b; 
        }
        
        /* Tables */
        .table-container { 
            background: #0f3460; 
            border-radius: 16px; 
            padding: 20px; 
            margin-bottom: 25px;
            border: 1px solid #1a1a4e;
            overflow-x: auto;
        }
        table { 
            width: 100%; 
            border-collapse: collapse; 
        }
        th, td { 
            padding: 12px 15px; 
            text-align: left; 
            border-bottom: 1px solid #1a1a4e; 
        }
        th { 
            background: #1a1a4e; 
            color: #ff6b6b; 
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.8rem;
            letter-spacing: 0.5px;
        }
        tr:hover { background: #1a1a4e; }
        
        /* Buttons */
        .btn { 
            padding: 8px 16px; 
            border: none; 
            border-radius: 8px; 
            cursor: pointer; 
            font-weight: 500;
            transition: all 0.2s;
            margin: 3px;
        }
        .btn-primary { background: #e94560; color: white; }
        .btn-primary:hover { background: #ff6b6b; }
        .btn-secondary { background: #0f3460; color: #e0e0e0; border: 1px solid #e94560; }
        .btn-secondary:hover { background: #1a1a4e; }
        .btn-danger { background: #c0392b; color: white; }
        .btn-danger:hover { background: #e74c3c; }
        .btn-success { background: #27ae60; color: white; }
        .btn-success:hover { background: #2ecc71; }
        
        /* Forms */
        .form-group { margin-bottom: 18px; }
        label { display: block; margin-bottom: 5px; color: #aaa; font-weight: 500; }
        input, select, textarea { 
            width: 100%; 
            padding: 12px 15px; 
            border-radius: 10px; 
            border: 1px solid #1a1a4e; 
            background: #0a0a1a; 
            color: white;
            font-size: 14px;
        }
        input:focus, select:focus, textarea:focus { 
            outline: none; 
            border-color: #e94560; 
        }
        
        /* Login */
        .login-container { 
            max-width: 400px; 
            margin: 120px auto; 
            background: #0f3460; 
            padding: 40px; 
            border-radius: 24px;
            border: 1px solid #e94560;
            box-shadow: 0 10px 40px rgba(233, 69, 96, 0.3);
        }
        
        /* Language switcher */
        .lang-switch { 
            display: flex; 
            gap: 8px; 
            margin-left: 15px; 
        }
        .lang-btn { 
            padding: 6px 12px; 
            border-radius: 6px; 
            background: transparent; 
            border: 1px solid #e94560; 
            color: #e0e0e0; 
            cursor: pointer;
        }
        .lang-btn.active { background: #e94560; color: white; }
        
        /* Tabs */
        .tabs { display: flex; gap: 2px; margin-bottom: 20px; }
        .tab { 
            padding: 10px 20px; 
            background: #0f3460; 
            border: none; 
            color: #e0e0e0; 
            cursor: pointer;
            border-radius: 8px 8px 0 0;
        }
        .tab.active { background: #e94560; color: white; }
        
        /* Status badges */
        .badge { 
            padding: 4px 10px; 
            border-radius: 20px; 
            font-size: 0.75rem; 
            font-weight: 600;
        }
        .badge-success { background: #27ae60; color: white; }
        .badge-danger { background: #c0392b; color: white; }
        .badge-warning { background: #f39c12; color: white; }
        
        /* Alerts */
        .alert { 
            padding: 15px 20px; 
            border-radius: 12px; 
            margin-bottom: 20px; 
        }
        .alert-success { background: #27ae60; color: white; }
        .alert-error { background: #c0392b; color: white; }
        
        /* Responsive */
        @media (max-width: 768px) {
            .nav { flex-direction: column; }
            .nav-right { margin-left: 0; flex-direction: column; }
            .stats-grid { grid-template-columns: 1fr 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        {% if not logged_in %}
            <div class="login-container">
                <h2 style="text-align:center; color:#ff6b6b; margin-bottom:25px;">{{ texts.login_title }}</h2>
                <form method="POST" action="/login">
                    <div class="form-group">
                        <label>{{ texts.password }}</label>
                        <input type="password" name="password" required autofocus>
                    </div>
                    <button type="submit" class="btn btn-primary" style="width:100%; padding:14px;">{{ texts.enter }}</button>
                </form>
                {% if error %}<p style="color:#e74c3c; text-align:center; margin-top:15px;">{{ error }}</p>{% endif %}
            </div>
        {% else %}
            <div class="nav">
                <a href="/" class="{% if active == 'dashboard' %}active{% endif %}">{{ texts.dashboard }}</a>
                <a href="/users" class="{% if active == 'users' %}active{% endif %}">{{ texts.users }}</a>
                <a href="/fumbles" class="{% if active == 'fumbles' %}active{% endif %}">{{ texts.fumbles }}</a>
                <a href="/broadcast" class="{% if active == 'broadcast' %}active{% endif %}">{{ texts.broadcast }}</a>
                <a href="/settings" class="{% if active == 'settings' %}active{% endif %}">{{ texts.settings }}</a>
                <div class="nav-right">
                    <div class="lang-switch">
                        <a href="/set_lang/en" class="lang-btn {% if lang == 'en' %}active{% endif %}">🇬🇧 EN</a>
                        <a href="/set_lang/ru" class="lang-btn {% if lang == 'ru' %}active{% endif %}">🇷🇺 RU</a>
                    </div>
                    <a href="/logout" style="color:#888;">{{ texts.logout }}</a>
                </div>
            </div>
            
            <h1>{{ texts.title }}</h1>
            
            {% block content %}{% endblock %}
        {% endif %}
    </div>
</body>
</html>
"""

# Dashboard template
DASHBOARD_TEMPLATE = """
{% extends "base" %}
{% block content %}
    <div class="stats-grid">
        <div class="stat-card">
            <h3>{{ texts.total_users }}</h3>
            <div class="value">{{ stats.total_users }}</div>
        </div>
        <div class="stat-card">
            <h3>{{ texts.total_fumbles }}</h3>
            <div class="value">{{ stats.total_fumbles }}</div>
        </div>
        <div class="stat-card">
            <h3>{{ texts.active_subs }}</h3>
            <div class="value">{{ stats.total_subs }}</div>
        </div>
        <div class="stat-card">
            <h3>{{ texts.avg_score }}</h3>
            <div class="value">{{ "%.1f"|format(stats.avg_score) }}</div>
        </div>
        <div class="stat-card">
            <h3>{{ texts.dau }}</h3>
            <div class="value">{{ stats.dau }}</div>
        </div>
        <div class="stat-card">
            <h3>{{ texts.mau }}</h3>
            <div class="value">{{ stats.mau }}</div>
        </div>
    </div>
    
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
        <div class="table-container">
            <h2>{{ texts.recent_users }}</h2>
            <table>
                <thead>
                    <tr>
                        <th>{{ texts.id }}</th>
                        <th>{{ texts.username }}</th>
                        <th>{{ texts.language }}</th>
                        <th>{{ texts.wallet }}</th>
                        <th>{{ texts.subscribed }}</th>
                    </tr>
                </thead>
                <tbody>
                    {% for user in recent_users %}
                    <tr>
                        <td><a href="/user/{{ user.user_id }}" style="color:#ff6b6b;">{{ user.user_id }}</a></td>
                        <td>{{ user.username or user.first_name or '-' }}</td>
                        <td>{{ user.language }}</td>
                        <td>{{ user.wallet_address[:8] if user.wallet_address else '-' }}...</td>
                        <td>{{ '✅' if user.subscribed else '❌' }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <div class="table-container">
            <h2>{{ texts.top_losers }}</h2>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>{{ texts.username }}</th>
                        <th>{{ texts.fumbles_count }}</th>
                        <th>{{ texts.score }}</th>
                    </tr>
                </thead>
                <tbody>
                    {% for user in top_losers %}
                    <tr>
                        <td>{{ loop.index }}</td>
                        <td>{{ user.user_id }}</td>
                        <td>{{ user.total_fumbles }}</td>
                        <td>{{ user.total_score }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
{% endblock %}
"""

USERS_TEMPLATE = """
{% extends "base" %}
{% block content %}
    <div class="table-container">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <h2 style="margin:0;">{{ texts.users }}</h2>
            <form method="GET" style="width: 300px;">
                <input type="text" name="search" placeholder="{{ texts.search_placeholder }}" value="{{ search }}">
            </form>
        </div>
        <table>
            <thead>
                <tr>
                    <th>{{ texts.id }}</th>
                    <th>{{ texts.username }}</th>
                    <th>{{ texts.language }}</th>
                    <th>{{ texts.level }}</th>
                    <th>{{ texts.fumbles_count }}</th>
                    <th>{{ texts.score }}</th>
                    <th>{{ texts.wallet }}</th>
                    <th>{{ texts.subscribed }}</th>
                    <th>{{ texts.actions }}</th>
                </tr>
            </thead>
            <tbody>
                {% for user in users %}
                <tr>
                    <td><a href="/user/{{ user.user_id }}" style="color:#ff6b6b;">{{ user.user_id }}</a></td>
                    <td>{{ user.username or user.first_name or '-' }}</td>
                    <td>{{ user.language }}</td>
                    <td>{{ user.level or 1 }}</td>
                    <td>{{ user.total_fumbles or 0 }}</td>
                    <td>{{ user.total_score or 0 }}</td>
                    <td>{{ user.wallet_address[:8] if user.wallet_address else '-' }}...</td>
                    <td>{{ '✅' if user.subscribed else '❌' }}</td>
                    <td>
                        <a href="/user/{{ user.user_id }}" class="btn btn-secondary btn-sm">{{ texts.view }}</a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% if page > 1 or has_next %}
        <div style="margin-top: 20px; display: flex; gap: 10px; justify-content: center;">
            {% if page > 1 %}
            <a href="?page={{ page - 1 }}&search={{ search }}" class="btn btn-secondary">← Previous</a>
            {% endif %}
            {% if has_next %}
            <a href="?page={{ page + 1 }}&search={{ search }}" class="btn btn-secondary">Next →</a>
            {% endif %}
        </div>
        {% endif %}
    </div>
{% endblock %}
"""

USER_DETAIL_TEMPLATE = """
{% extends "base" %}
{% block content %}
    <div class="table-container">
        <h2>{{ texts.user_details }}: {{ user.user_id }}</h2>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0;">
            <div>
                <h3>ℹ️ Info</h3>
                <p><strong>ID:</strong> {{ user.user_id }}</p>
                <p><strong>Username:</strong> {{ user.username or '-' }}</p>
                <p><strong>First name:</strong> {{ user.first_name or '-' }}</p>
                <p><strong>Language:</strong> {{ user.language }}</p>
                <p><strong>Joined:</strong> {{ user.created_at[:10] if user.created_at else '-' }}</p>
                <p><strong>Last active:</strong> {{ user.last_active or '-' }}</p>
            </div>
            <div>
                <h3>📊 {{ texts.stats }}</h3>
                <p><strong>Level:</strong> {{ user.level or 1 }}</p>
                <p><strong>Total fumbles:</strong> {{ user.total_fumbles or 0 }}</p>
                <p><strong>Total score:</strong> {{ user.total_score or 0 }}</p>
                <p><strong>Avg score:</strong> {{ "%.1f"|format(user.avg_score or 0) }}</p>
                <p><strong>Streak:</strong> {{ user.streak_days or 0 }} days (max: {{ user.max_streak or 0 }})</p>
                <p><strong>Wallet:</strong> {{ user.wallet_address or 'Not connected' }}</p>
                <p><strong>Subscribed:</strong> {{ '✅ Yes' if user.subscribed else '❌ No' }}</p>
            </div>
        </div>
        
        <div style="display: flex; gap: 10px; margin-bottom: 20px;">
            <form method="POST" action="/user/{{ user.user_id }}/action" style="display: inline;">
                <input type="hidden" name="action" value="toggle_block">
                <button type="submit" class="btn btn-warning">{{ texts.block if not user.is_blocked else texts.unblock }}</button>
            </form>
            <form method="POST" action="/user/{{ user.user_id }}/action" style="display: inline;">
                <input type="hidden" name="action" value="toggle_subscribe">
                <button type="submit" class="btn btn-secondary">{{ 'Unsubscribe' if user.subscribed else 'Subscribe' }}</button>
            </form>
            <form method="POST" action="/user/{{ user.user_id }}/action" style="display: inline;">
                <input type="hidden" name="action" value="reset_streak">
                <button type="submit" class="btn btn-danger" onclick="return confirm('Reset streak?')">Reset Streak</button>
            </form>
        </div>
        
        <h3>🏅 {{ texts.achievements }} ({{ achievements|length }})</h3>
        <div style="display: flex; flex-wrap: wrap; gap: 10px; margin: 15px 0;">
            {% for ach in achievements %}
            <span style="background: #1a1a4e; padding: 8px 15px; border-radius: 20px; border: 1px solid #e94560;">
                {{ ach.achievement_key }}
            </span>
            {% else %}
            <p>{{ texts.no_data }}</p>
            {% endfor %}
        </div>
        
        <h3>📋 {{ texts.referrals }}</h3>
        <p><strong>Invited by:</strong> {{ user.referral_by or '-' }}</p>
        <p><strong>Referrals count:</strong> {{ referrals_count }}</p>
    </div>
{% endblock %}
"""

BROADCAST_TEMPLATE = """
{% extends "base" %}
{% block content %}
    <div class="table-container" style="max-width: 700px;">
        <h2>{{ texts.broadcast_title }}</h2>
        {% if message %}
        <div class="alert alert-success">{{ message }}</div>
        {% endif %}
        <form method="POST">
            <div class="form-group">
                <label>{{ texts.broadcast_text }}</label>
                <textarea name="text" rows="5" required placeholder="Enter your message here..."></textarea>
            </div>
            <div class="form-group">
                <label>{{ texts.broadcast_photo }}</label>
                <input type="text" name="photo_url" placeholder="https://...">
            </div>
            <div class="form-group">
                <label>{{ texts.broadcast_target }}</label>
                <select name="target">
                    <option value="all">{{ texts.all_users }}</option>
                    <option value="subscribers">{{ texts.subscribers_only }}</option>
                </select>
            </div>
            <button type="submit" class="btn btn-primary">{{ texts.send }}</button>
        </form>
    </div>
{% endblock %}
"""

SETTINGS_TEMPLATE = """
{% extends "base" %}
{% block content %}
    <div class="tabs">
        <button class="tab active" onclick="showTab('memes')">{{ texts.memes_management }}</button>
        <button class="tab" onclick="showTab('stickers')">{{ texts.stickers_management }}</button>
        <button class="tab" onclick="showTab('achievements')">{{ texts.achievements_management }}</button>
        <button class="tab" onclick="showTab('quests')">{{ texts.quests_management }}</button>
    </div>
    
    <div id="memes" class="table-container tab-content">
        <h3>{{ texts.memes_management }}</h3>
        <form method="POST" action="/settings/memes">
            <div class="form-group" style="display: flex; gap: 10px;">
                <input type="text" name="url" placeholder="Meme URL" required style="flex: 1;">
                <button type="submit" class="btn btn-primary">{{ texts.add }}</button>
            </div>
        </form>
        <div style="display: flex; flex-wrap: wrap; gap: 15px; margin-top: 20px;">
            {% for meme in memes %}
            <div style="position: relative;">
                <img src="{{ meme.url }}" style="width: 150px; height: 150px; object-fit: cover; border-radius: 8px;">
                <a href="/settings/memes/delete/{{ meme.id }}" style="position: absolute; top: 5px; right: 5px; background: #c0392b; color: white; padding: 5px 8px; border-radius: 50%; text-decoration: none;">×</a>
            </div>
            {% endfor %}
        </div>
    </div>
    
    <div id="stickers" class="table-container tab-content" style="display:none;">
        <h3>{{ texts.stickers_management }}</h3>
        <p>Send stickers to @BintyBot with caption <code>/addsticker</code></p>
    </div>
    
    <div id="achievements" class="table-container tab-content" style="display:none;">
        <h3>{{ texts.achievements_management }}</h3>
        <table>
            <thead>
                <tr>
                    <th>Key</th>
                    <th>Name (EN)</th>
                    <th>Reward</th>
                    <th>Active</th>
                </tr>
            </thead>
            <tbody>
                {% for ach in achievements_list %}
                <tr>
                    <td>{{ ach.achievement_key }}</td>
                    <td>{{ ach.name_en }}</td>
                    <td>{{ ach.reward_points }}</td>
                    <td>{{ '✅' if ach.is_active else '❌' }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    
    <div id="quests" class="table-container tab-content" style="display:none;">
        <h3>{{ texts.quests_management }}</h3>
        <table>
            <thead>
                <tr>
                    <th>Key</th>
                    <th>Name (EN)</th>
                    <th>Condition</th>
                    <th>Reward</th>
                    <th>Active</th>
                </tr>
            </thead>
            <tbody>
                {% for quest in quests %}
                <tr>
                    <td>{{ quest.quest_key }}</td>
                    <td>{{ quest.name_en }}</td>
                    <td>{{ quest.condition_type }}: {{ quest.condition_value }}</td>
                    <td>{{ quest.reward_points }} pts</td>
                    <td>{{ '✅' if quest.is_active else '❌' }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    
    <script>
        function showTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
            document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).style.display = 'block';
            event.target.classList.add('active');
        }
    </script>
{% endblock %}
"""

# Routes
@app.context_processor
def inject_texts():
    lang = session.get("lang", "en")
    return {"texts": TEXTS[lang], "lang": lang}

@app.route("/set_lang/<lang>")
def set_lang(lang):
    if lang in ["en", "ru"]:
        session["lang"] = lang
    return redirect(request.referrer or url_for("index"))

@app.route("/")
def index():
    if not session.get("logged_in"):
        return render_template_string(HTML_TEMPLATE, logged_in=False)
    
    # Get stats
    stats = {"total_users": 0, "total_fumbles": 0, "total_subs": 0, "avg_score": 0, "dau": 0, "mau": 0}
    recent_users = []
    top_losers = []
    
    if supabase:
        try:
            # Total users
            res = supabase.table("users").select("*", count="exact").execute()
            stats["total_users"] = res.count or 0
            
            # Total fumbles
            res = supabase.table("fumbles").select("*", count="exact").execute()
            stats["total_fumbles"] = res.count or 0
            
            # Active subs
            res = supabase.table("users").select("*", count="exact").eq("subscribed", True).execute()
            stats["total_subs"] = res.count or 0
            
            # Avg score
            res = supabase.table("user_stats").select("avg_score").execute()
            if res.data:
                avg = sum(s.get("avg_score", 0) for s in res.data) / len(res.data) if res.data else 0
                stats["avg_score"] = avg
            
            # DAU
            today = datetime.now().date().isoformat()
            res = supabase.table("users").select("*", count="exact").eq("last_active", today).execute()
            stats["dau"] = res.count or 0
            
            # MAU
            month_ago = (datetime.now() - timedelta(days=30)).date().isoformat()
            res = supabase.table("users").select("*", count="exact").gte("last_active", month_ago).execute()
            stats["mau"] = res.count or 0
            
            # Recent users
            res = supabase.table("users").select("*").order("created_at", desc=True).limit(10).execute()
            recent_users = res.data or []
            
            # Top losers
            res = supabase.table("user_stats").select("user_id,total_fumbles,total_score").order("total_score", desc=True).limit(10).execute()
            top_losers = res.data or []
            
        except Exception as e:
            logger.error(f"DB Error: {e}")
    
    return render_template_string(
        HTML_TEMPLATE.replace('{% block content %}{% endblock %}', DASHBOARD_TEMPLATE),
        logged_in=True, stats=stats, recent_users=recent_users, top_losers=top_losers, active="dashboard"
    )

@app.route("/login", methods=["POST"])
def login():
    if request.form.get("password") == ADMIN_PASSWORD:
        session["logged_in"] = True
        session["lang"] = session.get("lang", "en")
        return redirect(url_for("index"))
    return render_template_string(HTML_TEMPLATE, logged_in=False, error=TEXTS[session.get("lang", "en")]["wrong_password"])

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)