import sqlite3
import os
import logging
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'fumbl.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Enhanced Users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        lang TEXT DEFAULT 'en',
        wallet_address TEXT,
        is_subscribed INTEGER DEFAULT 0,
        total_score INTEGER DEFAULT 0,
        fumble_count INTEGER DEFAULT 0,
        interaction_count INTEGER DEFAULT 0,
        mood_level INTEGER DEFAULT 0, -- 0: Bored, 1: Annoyed, 2: Angry, 3: Psychotic
        last_action TEXT,
        referrer_id INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Fumbles history
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS fumbles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        score INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Referrals table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        referred_id INTEGER UNIQUE,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (referrer_id) REFERENCES users (user_id),
        FOREIGN KEY (referred_id) REFERENCES users (user_id)
    )
    ''')
    
    conn.commit()
    conn.close()
    logging.info("Database initialized with enhanced memory.")

def get_user_data(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_interaction(user_id, action_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create user if not exists
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    
    # Update stats
    cursor.execute("""
        UPDATE users SET 
            interaction_count = interaction_count + 1,
            last_action = ?,
            last_seen = ?,
            mood_level = CASE 
                WHEN interaction_count > 100 THEN 3
                WHEN interaction_count > 50 THEN 2
                WHEN interaction_count > 10 THEN 1
                ELSE 0 
            END
        WHERE user_id = ?
    """, (action_name, now, user_id))
    
    conn.commit()
    conn.close()

def get_language(user_id):
    data = get_user_data(user_id)
    return data['lang'] if data else 'en'

def set_language(user_id, lang):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (user_id, lang) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET lang = ?", (user_id, lang, lang))
    conn.commit()
    conn.close()

def save_fumble(user_id, score):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, total_score, fumble_count) 
        VALUES (?, ?, 1) 
        ON CONFLICT(user_id) DO UPDATE SET 
            total_score = total_score + ?, 
            fumble_count = fumble_count + 1
    """, (user_id, score, score))
    cursor.execute("INSERT INTO fumbles (user_id, score) VALUES (?, ?)", (user_id, score))
    conn.commit()
    conn.close()

def get_user_stats(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT total_score, fumble_count, interaction_count, mood_level FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
    ref_count = cursor.fetchone()[0]
    
    conn.close()
    if row:
        stats = dict(row)
        stats['referrals'] = ref_count
        return stats
    return {"total_score": 0, "fumble_count": 0, "interaction_count": 0, "mood_level": 0, "referrals": ref_count}

def get_leaderboard(limit=5, offset=0):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, fumble_count, total_score FROM users ORDER BY total_score DESC LIMIT ? OFFSET ?", (limit, offset))
    rows = cursor.fetchall()
    conn.close()
    return [(r['user_id'], r['fumble_count'], r['total_score']) for r in rows]

def get_leaderboard_count():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_user_position(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) + 1 FROM users WHERE total_score > (SELECT total_score FROM users WHERE user_id = ?)", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def subscribe_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (user_id, is_subscribed) VALUES (?, 1) ON CONFLICT(user_id) DO UPDATE SET is_subscribed = 1", (user_id,))
    conn.commit()
    conn.close()

def unsubscribe_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_subscribed = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def is_subscribed(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_subscribed FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return bool(row['is_subscribed']) if row else False

def save_wallet_address(user_id, address):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (user_id, wallet_address) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET wallet_address = ?", (user_id, address, address))
    conn.commit()
    conn.close()

def get_wallet_address(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT wallet_address FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row['wallet_address'] if row else None

def add_referral(referrer_id, referred_id):
    if referrer_id == referred_id:
        return False
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)", (referrer_id, referred_id))
        cursor.execute("UPDATE users SET referrer_id = ? WHERE user_id = ?", (referrer_id, referred_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()
