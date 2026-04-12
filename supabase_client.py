import os
import json
import logging
import random
import aiohttp
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List, Tuple
from supabase import create_client, Client

# Инициализация Supabase
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase: Client = None

def init_supabase():
    """Инициализирует клиент Supabase"""
    global supabase
    if url and key:
        supabase = create_client(url, key)
        logging.info("Supabase client initialized")
    else:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

# ==================== ПОЛЬЗОВАТЕЛИ ====================

async def get_user(user_id: int) -> Optional[Dict]:
    """Получает данные пользователя"""
    try:
        res = supabase.table("users").select("*").eq("user_id", user_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logging.error(f"Error getting user {user_id}: {e}")
        return None

async def create_user(user_id: int, username: str, first_name: str, lang: str = "en") -> Dict:
    """Создаёт нового пользователя"""
    data = {
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "language": lang,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    try:
        supabase.table("users").insert(data).execute()
        # Создаём запись в user_stats
        supabase.table("user_stats").insert({
            "user_id": user_id,
            "total_fumbles": 0,
            "total_score": 0,
            "avg_score": 0,
            "signal_clicks": 0,
            "price_checks": 0,
            "portfolio_views": 0,
            "rare_phrases": 0,
            "total_loss_usd": 0
        }).execute()
        return data
    except Exception as e:
        logging.error(f"Error creating user {user_id}: {e}")
        raise

async def update_user(user_id: int, **kwargs) -> bool:
    """Обновляет данные пользователя"""
    try:
        kwargs["updated_at"] = datetime.now().isoformat()
        supabase.table("users").update(kwargs).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        logging.error(f"Error updating user {user_id}: {e}")
        return False

async def delete_user(user_id: int) -> bool:
    """Удаляет пользователя"""
    try:
        supabase.table("users").delete().eq("user_id", user_id).execute()
        return True
    except Exception as e:
        logging.error(f"Error deleting user {user_id}: {e}")
        return False
        
# ==================== МЕМЫ =======

async def get_random_meme():
    try:
        res = supabase.table("memes").select("url").execute()
        if res.data:
            return random.choice(res.data)["url"]
    except:
        pass
    return "https://i.imgflip.com/2kbnrp.jpg"  # fallback

# ==================== ЯЗЫКИ ====================

async def get_language(user_id: int) -> str:
    """Возвращает язык пользователя"""
    user = await get_user(user_id)
    return user.get("language", "en") if user else "en"

async def set_language(user_id: int, lang: str) -> bool:
    """Устанавливает язык пользователя"""
    return await update_user(user_id, language=lang)

# ==================== КОШЕЛЬКИ ====================

async def save_wallet_address(user_id: int, address: str) -> bool:
    """Сохраняет адрес кошелька"""
    return await update_user(user_id, wallet_address=address, wallet_connected_at=datetime.now().isoformat())

async def get_wallet_address(user_id: int) -> Optional[str]:
    """Возвращает сохранённый адрес кошелька"""
    user = await get_user(user_id)
    return user.get("wallet_address") if user else None

async def delete_wallet_address(user_id: int) -> bool:
    """Удаляет адрес кошелька"""
    return await update_user(user_id, wallet_address=None)

# ==================== ПОДПИСКИ ====================

async def subscribe_user(user_id: int) -> bool:
    """Подписывает пользователя на авто-сигналы"""
    return await update_user(user_id, subscribed=True, subscription_date=datetime.now().isoformat())

async def unsubscribe_user(user_id: int) -> bool:
    """Отписывает пользователя от авто-сигналов"""
    return await update_user(user_id, subscribed=False)

async def is_subscribed(user_id: int) -> bool:
    """Проверяет подписку"""
    user = await get_user(user_id)
    return user.get("subscribed", False) if user else False

async def get_all_subscribed_users() -> List[int]:
    """Возвращает список всех подписанных пользователей"""
    try:
        res = supabase.table("users").select("user_id").eq("subscribed", True).execute()
        return [row["user_id"] for row in res.data]
    except Exception as e:
        logging.error(f"Error getting subscribed users: {e}")
        return []

# ==================== ФАМБЛЫ ====================

async def save_fumble(user_id: int, score: int, type: str = "manual", details: Dict = None) -> bool:
    """Сохраняет фамбл и обновляет статистику"""
    try:
        # Сохраняем фамбл
        data = {
            "user_id": user_id,
            "score": score,
            "type": type,
            "details": json.dumps(details) if details else None,
            "created_at": datetime.now().isoformat()
        }
        supabase.table("fumbles").insert(data).execute()
        
        # Обновляем статистику пользователя
        await update_user_stats(user_id, score, details)
        
        return True
    except Exception as e:
        logging.error(f"Error saving fumble for {user_id}: {e}")
        return False

async def update_user_stats(user_id: int, score: int = None, details: Dict = None):
    """Обновляет статистику пользователя после фамбла"""
    try:
        # Получаем текущую статистику
        res = supabase.table("user_stats").select("*").eq("user_id", user_id).execute()
        if not res.data:
            # Создаём если нет
            supabase.table("user_stats").insert({"user_id": user_id}).execute()
            stats = {"total_fumbles": 0, "total_score": 0, "total_loss_usd": 0}
        else:
            stats = res.data[0]
        
        updates = {}
        if score is not None:
            new_count = stats.get("total_fumbles", 0) + 1
            new_total = stats.get("total_score", 0) + score
            updates["total_fumbles"] = new_count
            updates["total_score"] = new_total
            updates["avg_score"] = new_total / new_count if new_count > 0 else 0
        
        if details:
            pnl = details.get("pnl_usd", 0)
            if pnl < 0:
                updates["total_loss_usd"] = stats.get("total_loss_usd", 0) + abs(pnl)
        
        if updates:
            supabase.table("user_stats").update(updates).eq("user_id", user_id).execute()
            
    except Exception as e:
        logging.error(f"Error updating user stats for {user_id}: {e}")

async def get_user_stats(user_id: int) -> Optional[Dict]:
    """Возвращает статистику пользователя"""
    try:
        res = supabase.table("user_stats").select("*").eq("user_id", user_id).execute()
        if res.data:
            stats = res.data[0]
            return {
                "average": stats.get("avg_score", 0),
                "count": stats.get("total_fumbles", 0),
                "total_score": stats.get("total_score", 0),
                "signal_clicks": stats.get("signal_clicks", 0)
            }
        return None
    except Exception as e:
        logging.error(f"Error getting user stats for {user_id}: {e}")
        return None

async def get_fumble_history(user_id: int, limit: int = 10) -> List[Dict]:
    """Возвращает историю фамблов"""
    try:
        res = supabase.table("fumbles").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
        return res.data
    except Exception as e:
        logging.error(f"Error getting fumble history for {user_id}: {e}")
        return []
        
# ==================== ВЛИЯНИЕ СИГНАЛА НА ФАМБЛ ====================

async def check_signal_fumble_bonus(user_id: int) -> int:
    """Проверяет, был ли сигнал в последний час, и возвращает бонус +1 если да"""
    try:
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        res = supabase.table("signal_history").select("created_at").eq("user_id", user_id).gte("created_at", one_hour_ago).execute()
        return 1 if res.data else 0
    except:
        return 0

# ==================== ЛИДЕРБОРД ====================

async def get_leaderboard(limit: int = 10, offset: int = 0) -> List[Tuple]:
    """Возвращает топ пользователей по total_score"""
    try:
        res = supabase.table("user_stats").select("user_id, total_fumbles, total_score").order("total_score", desc=True).range(offset, offset + limit - 1).execute()
        return [(row["user_id"], row["total_fumbles"], row["total_score"]) for row in res.data]
    except Exception as e:
        logging.error(f"Error getting leaderboard: {e}")
        return []

async def get_leaderboard_count() -> int:
    """Возвращает количество пользователей в лидерборде"""
    try:
        res = supabase.table("user_stats").select("user_id", count="exact").execute()
        return res.count if res.count else 0
    except Exception as e:
        logging.error(f"Error getting leaderboard count: {e}")
        return 0

async def get_user_position(user_id: int) -> int:
    """Возвращает позицию пользователя в лидерборде"""
    try:
        res = supabase.rpc('get_user_leaderboard_position', {'p_user_id': user_id}).execute()
        return res.data if res.data else 999
    except Exception as e:
        logging.error(f"Error getting user position: {e}")
        return 999

# ==================== СТРИК (КАЛЕНДАРЬ СТРАДАНИЙ) ====================

async def update_streak(user_id: int) -> Dict:
    """Обновляет ежедневный стрик пользователя"""
    try:
        user = await get_user(user_id)
        if not user:
            return {"current_streak": 0, "max_streak": 0, "bonus_given": False}
        
        today = date.today().isoformat()
        last_active = user.get("last_active")
        streak = user.get("streak_days", 0)
        max_streak = user.get("max_streak", 0)
        calendar = user.get("calendar_json") or {}
        
        bonus_given = False
        
        if last_active == today:
            # Уже активен сегодня
            pass
        elif last_active == (date.today() - timedelta(days=1)).isoformat():
            # Продолжаем серию
            streak += 1
            max_streak = max(max_streak, streak)
            
            # Бонус каждые 7 дней
            if streak % 7 == 0:
                # Добавляем бонусный балл
                supabase.table("user_stats").update({
                    "total_score": supabase.rpc('increment_score', {'p_user_id': user_id, 'p_amount': 1})
                }).eq("user_id", user_id).execute()
                bonus_given = True
        else:
            # Серия прервана
            streak = 1
        
        calendar[today] = 1
        
        await update_user(
            user_id,
            last_active=today,
            streak_days=streak,
            max_streak=max_streak,
            calendar_json=calendar
        )
        
        return {
            "current_streak": streak,
            "max_streak": max_streak,
            "bonus_given": bonus_given
        }
        
    except Exception as e:
        logging.error(f"Error updating streak for {user_id}: {e}")
        return {"current_streak": 0, "max_streak": 0, "bonus_given": False}

async def get_streak_info(user_id: int) -> Dict:
    """Возвращает информацию о стрике"""
    try:
        user = await get_user(user_id)
        if not user:
            return {"current_streak": 0, "max_streak": 0, "active_days": []}
        
        calendar = user.get("calendar_json") or {}
        active_days = [day for day, val in calendar.items() if val]
        active_days.sort(reverse=True)
        
        return {
            "current_streak": user.get("streak_days", 0),
            "max_streak": user.get("max_streak", 0),
            "active_days": active_days[:30]
        }
    except Exception as e:
        logging.error(f"Error getting streak info for {user_id}: {e}")
        return {"current_streak": 0, "max_streak": 0, "active_days": []}

# ==================== СИГНАЛЫ ====================

async def save_signal_history(user_id: int, signal_text: str, is_rare: bool = False) -> bool:
    """Сохраняет сигнал в историю"""
    try:
        data = {
            "user_id": user_id,
            "signal_text": signal_text,
            "is_rare": is_rare,
            "created_at": datetime.now().isoformat()
        }
        supabase.table("signal_history").insert(data).execute()
        
        # Увеличиваем счётчик сигналов
        stats = supabase.table("user_stats").select("signal_clicks").eq("user_id", user_id).execute()
        if stats.data:
            current = stats.data[0].get("signal_clicks", 0)
            supabase.table("user_stats").update({"signal_clicks": current + 1}).eq("user_id", user_id).execute()
        else:
            supabase.table("user_stats").insert({"user_id": user_id, "signal_clicks": 1}).execute()
                
        if is_rare:
            stats = supabase.table("user_stats").select("rare_phrases").eq("user_id", user_id).execute()
            if stats.data:
                current = stats.data[0].get("rare_phrases", 0)
                supabase.table("user_stats").update({"rare_phrases": current + 1}).eq("user_id", user_id).execute()
            else:
                supabase.table("user_stats").insert({"user_id": user_id, "rare_phrases": 1}).execute()
        
        return True
    except Exception as e:
        logging.error(f"Error saving signal history for {user_id}: {e}")
        return False

async def get_signal_history(user_id: int, limit: int = 10) -> List[Dict]:
    """Возвращает историю сигналов"""
    try:
        res = supabase.table("signal_history").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
        return res.data
    except Exception as e:
        logging.error(f"Error getting signal history for {user_id}: {e}")
        return []
        
    
# ==================== СИГНАЛ ДНЯ И АВТО-СИГНАЛЫ ====================

async def get_signal_of_the_day() -> str:
    """Возвращает случайный сигнал дня из истории"""
    try:
        res = supabase.table("signal_history").select("signal_text").order("created_at", desc=True).limit(100).execute()
        if res.data:
            return random.choice(res.data)["signal_text"]
    except:
        pass
    return "Buy high, sell low. You know the drill. 💀"

async def send_signal_of_the_day():
    """Отправляет сигнал дня всем подписчикам"""
    from texts import get_text, add_hooks
    import telegram
    
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return
    
    bot = telegram.Bot(token=bot_token)
    subscribers = await get_all_subscribed_users()
    signal_text = await get_signal_of_the_day()
    
    for user_id in subscribers:
        try:
            lang = await get_language(user_id)
            text = f"📡 **Signal of the Day**\n\n{signal_text}\n\n*Sent to all subscribers. Suffer together.*"
            final_text = add_hooks(lang, text)
            await bot.send_message(chat_id=user_id, text=final_text, parse_mode="Markdown")
        except:
            pass

async def send_auto_signals():
    """Отправляет авто-сигналы всем подписчикам (каждые 6 часов)"""
    import telegram
    from texts import get_text, add_hooks
    
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return
    
    bot = telegram.Bot(token=bot_token)
    subscribers = await get_all_subscribed_users()
    
    for user_id in subscribers:
        try:
            lang = await get_language(user_id)
            signal_text = get_text(lang, "signal")
            text = get_text(lang, "auto_signal", signal_text)
            final_text = add_hooks(lang, text)
            await bot.send_message(chat_id=user_id, text=final_text, parse_mode="Markdown")
        except:
            pass

# ==================== РЕФЕРАЛЫ ====================

async def create_referral(referrer_id: int, referred_id: int) -> bool:
    """Создаёт реферальную связь"""
    try:
        # Проверяем, нет ли уже такой связи
        existing = supabase.table("referrals").select("id").eq("referrer_id", referrer_id).eq("referred_id", referred_id).execute()
        if existing.data:
            return False
        
        data = {
            "referrer_id": referrer_id,
            "referred_id": referred_id,
            "created_at": datetime.now().isoformat()
        }
        supabase.table("referrals").insert(data).execute()
        
        # Обновляем referral_by у приглашённого
        await update_user(referred_id, referral_by=referrer_id)
        
        return True
    except Exception as e:
        logging.error(f"Error creating referral: {e}")
        return False

async def get_referrals_count(user_id: int) -> int:
    """Возвращает количество приглашённых пользователей"""
    try:
        res = supabase.table("referrals").select("id", count="exact").eq("referrer_id", user_id).execute()
        return res.count if res.count else 0
    except Exception as e:
        logging.error(f"Error getting referrals count for {user_id}: {e}")
        return 0

async def give_referral_bonus(referrer_id: int, referred_id: int):
    """Начисляет бонус за реферала при первом фамбле"""
    try:
        # Проверяем, не начислен ли уже бонус
        ref = supabase.table("referrals").select("reward_given").eq("referrer_id", referrer_id).eq("referred_id", referred_id).execute()
        if ref.data and ref.data[0].get("reward_given"):
            return
        
        # Начисляем виртуальные BINTY
        # Реферер получает 100, приглашённый 50
        supabase.table("user_balances").upsert({
            "user_id": referrer_id,
            "amount": supabase.rpc('increment_balance', {'p_user_id': referrer_id, 'p_amount': 100})
        }).execute()
        
        supabase.table("user_balances").upsert({
            "user_id": referred_id,
            "amount": supabase.rpc('increment_balance', {'p_user_id': referred_id, 'p_amount': 50})
        }).execute()
        
        # Отмечаем, что бонус выдан
        supabase.table("referrals").update({"reward_given": True}).eq("referrer_id", referrer_id).eq("referred_id", referred_id).execute()
        
    except Exception as e:
        logging.error(f"Error giving referral bonus: {e}")

# ==================== АЧИВКИ ====================

async def save_achievement(user_id: int, achievement_key: str) -> bool:
    """Сохраняет полученную ачивку"""
    try:
        data = {
            "user_id": user_id,
            "achievement_key": achievement_key,
            "earned_at": datetime.now().isoformat()
        }
        supabase.table("user_achievements").insert(data).execute()
        return True
    except Exception as e:
        logging.error(f"Error saving achievement {achievement_key} for {user_id}: {e}")
        return False

async def get_user_achievements(user_id: int) -> List[Dict]:
    """Возвращает список полученных ачивок"""
    try:
        res = supabase.table("user_achievements").select("*").eq("user_id", user_id).execute()
        return res.data
    except Exception as e:
        logging.error(f"Error getting achievements for {user_id}: {e}")
        return []
        
async def get_all_achievements(lang: str = "en") -> List[Dict]:
    """Возвращает список всех ачивок"""
    try:
        res = supabase.table("achievements_list").select("*").execute()
        return res.data if res.data else []
    except Exception as e:
        logging.error(f"Error getting all achievements: {e}")
        return []

# ==================== КВЕСТЫ ====================

async def get_active_quests(user_id: int) -> List[Dict]:
    """Возвращает активные квесты для пользователя"""
    try:
        # Получаем глобальные активные квесты
        res = supabase.table("quests").select("*").eq("is_active", True).execute()
        quests = res.data
        
        # Получаем прогресс пользователя
        user_quests = supabase.table("user_quests").select("*").eq("user_id", user_id).execute()
        progress_map = {q["quest_id"]: q for q in user_quests.data}
        
        for quest in quests:
            quest["progress"] = progress_map.get(quest["id"], {}).get("progress", 0)
            quest["completed"] = progress_map.get(quest["id"], {}).get("completed", False)
        
        return quests
    except Exception as e:
        logging.error(f"Error getting quests for {user_id}: {e}")
        return []

async def update_quest_progress(user_id: int, quest_id: int, progress: int) -> bool:
    """Обновляет прогресс квеста"""
    try:
        quest = supabase.table("quests").select("*").eq("id", quest_id).single().execute()
        if not quest.data:
            return False
        
        completed = progress >= quest.data["condition_value"]
        
        data = {
            "user_id": user_id,
            "quest_id": quest_id,
            "progress": progress,
            "completed": completed,
            "completed_at": datetime.now().isoformat() if completed else None
        }
        
        supabase.table("user_quests").upsert(data).execute()
        
        if completed:
            # Начисляем награду
            reward = quest.data["reward_points"]
            stats = supabase.table("user_stats").select("total_score").eq("user_id", user_id).execute()
            if stats.data:
                current = stats.data[0].get("total_score", 0)
                supabase.table("user_stats").update({"total_score": current + reward}).eq("user_id", user_id).execute()
            else:
                supabase.table("user_stats").insert({"user_id": user_id, "total_score": reward}).execute()
        
        return True
    except Exception as e:
        logging.error(f"Error updating quest progress: {e}")
        return False

# ==================== СЕРТИФИКАТ ====================

async def log_certificate_request(user_id: int) -> bool:
    """Логирует запрос сертификата"""
    try:
        data = {
            "user_id": user_id,
            "created_at": datetime.now().isoformat()
        }
        supabase.table("certificate_requests").insert(data).execute()
        return True
    except Exception as e:
        logging.error(f"Error logging certificate request: {e}")
        return False

# ==================== АЧИВКИ (ПРОВЕРКА И ВЫДАЧА) ====================

# Импортируем в конец файла, чтобы избежать циклических импортов
from texts import get_text

# ==================== ШУТКИ ПРО ПОРТФЕЛЬ ====================

async def get_portfolio_roast(address: str, lang: str = "en") -> str:
    """Возвращает саркастичный комментарий про портфель"""
    try:
        # Получаем все токены на кошельке
        url = f"https://public-api.solscan.io/account/tokens?account={address}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as resp:
                tokens = await resp.json()
                
        if not tokens:
            ROASTS = {
                "en": ["Empty wallet. Like your brain.", "Nothing here. Just like your trading skills."],
                "ru": ["Пустой кошелёк. Как твоя голова.", "Ничего нет. Как и твоих навыков."],
                "es": ["Cartera vacía. Como tu cerebro.", "Nada aquí. Como tus habilidades."],
                "zh": ["空钱包。像你的脑袋。", "什么都没有。就像你的技能。"]
            }
            return random.choice(ROASTS.get(lang, ROASTS["en"]))
        
        # Считаем количество токенов
        count = len(tokens)
        if count > 10:
            ROASTS = {
                "en": [f"{count} tokens? You're a collector of garbage.", "Diversified portfolio of shitcoins. Impressive."],
                "ru": [f"{count} токенов? Коллекционер мусора.", "Диверсифицированный портфель шиткоинов. Впечатляет."],
                "es": [f"{count} tokens? Coleccionista de basura.", "Cartera diversificada de mierdacoins. Impresionante."],
                "zh": [f"{count}个代币？垃圾收藏家。", "多元化的垃圾币组合。令人印象深刻。"]
            }
            return random.choice(ROASTS.get(lang, ROASTS["en"]))
        elif count > 3:
            ROASTS = {
                "en": [f"{count} tokens. All red, I assume.", "A few bags. Heavy ones."],
                "ru": [f"{count} токена. Все в минус, полагаю.", "Несколько мешков. Тяжёлых."],
                "es": [f"{count} tokens. Todos en rojo, asumo.", "Unas cuantas bolsas. Pesadas."],
                "zh": [f"{count}个代币。我猜全在亏损。", "几个袋子。很重。"]
            }
            return random.choice(ROASTS.get(lang, ROASTS["en"]))
        else:
            ROASTS = {
                "en": ["Just one token? All eggs in one basket. Dumb.", "No diversification. Brave. And stupid."],
                "ru": ["Один токен? Все яйца в одной корзине. Глупо.", "Никакой диверсификации. Смело. И тупо."],
                "es": ["¿Un solo token? Todos los huevos en una cesta. Tonto.", "Sin diversificación. Valiente. Y estúpido."],
                "zh": ["只有一个代币？所有鸡蛋放一个篮子。蠢。", "没有多元化。勇敢。且愚蠢。"]
            }
            return random.choice(ROASTS.get(lang, ROASTS["en"]))
            
    except:
        ROASTS = {
            "en": ["Can't even check your wallet. Pathetic.", "Wallet check failed. Like everything you do."],
            "ru": ["Даже кошелёк проверить не могу. Жалко.", "Проверка не удалась. Как и всё, что ты делаешь."],
            "es": ["Ni siquiera puedo revisar tu cartera. Patético.", "Falló la verificación. Como todo lo que haces."],
            "zh": ["连钱包都查不了。可悲。", "检查失败。就像你做的一切。"]
        }
        return random.choice(ROASTS.get(lang, ROASTS["en"]))

# ==================== КВЕСТЫ (ПОЛНАЯ СИСТЕМА) ====================

async def generate_daily_quests_for_user(user_id: int) -> List[Dict]:
    """Генерирует ежедневные квесты для пользователя"""
    try:
        # Получаем все активные квесты с duration_hours <= 24 (ежедневные)
        res = supabase.table("quests").select("*").eq("is_active", True).lte("duration_hours", 24).execute()
        quests = res.data
        
        assigned_quests = []
        now = datetime.now()
        
        for quest in quests:
            # Проверяем, не назначен ли уже такой квест сегодня
            existing = supabase.table("user_quests").select("id").eq("user_id", user_id).eq("quest_id", quest["id"]).gte("assigned_at", now.date().isoformat()).execute()
            
            if not existing.data:
                # Назначаем квест
                expires_at = now + timedelta(hours=quest["duration_hours"])
                data = {
                    "user_id": user_id,
                    "quest_id": quest["id"],
                    "assigned_at": now.isoformat(),
                    "expires_at": expires_at.isoformat(),
                    "progress": 0,
                    "completed": False,
                    "reward_claimed": False
                }
                supabase.table("user_quests").insert(data).execute()
                assigned_quests.append(quest)
        
        return assigned_quests
    except Exception as e:
        logging.error(f"Error generating quests for {user_id}: {e}")
        return []


async def update_quest_progress(user_id: int, condition_type: str, increment: int = 1):
    """Обновляет прогресс всех активных квестов пользователя по типу условия"""
    try:
        now = datetime.now().isoformat()
        
        # Получаем активные квесты пользователя с данным типом условия
        res = supabase.table("user_quests").select("*, quests(*)").eq("user_id", user_id).eq("completed", False).lte("assigned_at", now).gte("expires_at", now).execute()
        
        if not res.data:
            return
        
        for user_quest in res.data:
            quest = user_quest.get("quests", {})
            if quest.get("condition_type") == condition_type:
                new_progress = user_quest["progress"] + increment
                completed = new_progress >= quest["condition_value"]
                
                update_data = {"progress": new_progress}
                if completed:
                    update_data["completed"] = True
                    update_data["completed_at"] = now
                
                supabase.table("user_quests").update(update_data).eq("id", user_quest["id"]).execute()
                
                # Если квест выполнен, отправляем уведомление
                if completed:
                    await notify_quest_completed(user_id, quest)
                    
    except Exception as e:
        logging.error(f"Error updating quest progress for {user_id}: {e}")


async def claim_quest_reward(user_id: int, user_quest_id: int) -> Dict:
    """Забирает награду за выполненный квест"""
    try:
        # Получаем квест
        res = supabase.table("user_quests").select("*, quests(*)").eq("id", user_quest_id).eq("user_id", user_id).single().execute()
        
        if not res.data:
            return {"success": False, "error": "Quest not found"}
        
        user_quest = res.data
        if not user_quest["completed"]:
            return {"success": False, "error": "Quest not completed"}
        if user_quest["reward_claimed"]:
            return {"success": False, "error": "Reward already claimed"}
        
        quest = user_quest.get("quests", {})
        reward_points = quest.get("reward_points", 0)
        reward_binty = quest.get("reward_binty", 0)
        
        # Начисляем баллы (прямой запрос к RPC, результат получаем отдельно)
        if reward_points > 0:
            score_res = supabase.rpc('increment_score', {'p_user_id': user_id, 'p_amount': reward_points}).execute()
            # RPC уже выполнен, обновлять таблицу не нужно (функция сама обновляет)
        
        # Начисляем BINTY
        if reward_binty > 0:
            balance_res = supabase.rpc('increment_balance', {'p_user_id': user_id, 'p_amount': reward_binty}).execute()
        
        # Отмечаем награду как полученную
        supabase.table("user_quests").update({"reward_claimed": True}).eq("id", user_quest_id).execute()
        
        return {
            "success": True,
            "reward_points": reward_points,
            "reward_binty": reward_binty,
            "quest_name": quest.get("name_en", "Quest")
        }
        
    except Exception as e:
        logging.error(f"Error claiming quest reward: {e}")
        return {"success": False, "error": str(e)}

async def get_user_active_quests(user_id: int) -> List[Dict]:
    """Возвращает активные (незавершённые или незаклеймленные) квесты пользователя"""
    try:
        now = datetime.now().isoformat()
        res = supabase.table("user_quests").select("*, quests(*)") \
            .eq("user_id", user_id) \
            .lte("assigned_at", now) \
            .gte("expires_at", now) \
            .or_("completed.eq.false,reward_claimed.eq.false") \
            .execute()
        return res.data if res.data else []
    except Exception as e:
        logging.error(f"Error getting active quests: {e}")
        return []

async def get_user_completed_quests(user_id: int, limit: int = 5) -> List[Dict]:
    """Возвращает выполненные квесты пользователя"""
    try:
        res = supabase.table("user_quests").select("*, quests(*)").eq("user_id", user_id).eq("completed", True).order("completed_at", desc=True).limit(limit).execute()
        return res.data if res.data else []
    except Exception as e:
        logging.error(f"Error getting completed quests: {e}")
        return []


async def notify_quest_completed(user_id: int, quest: Dict):
    """Отправляет уведомление о выполнении квеста и удаляет его через 5 секунд"""
    try:
        lang = await get_language(user_id)
        name = quest.get(f"name_{lang}", quest.get("name_en", "Quest"))
        
        import telegram
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if bot_token:
            bot = telegram.Bot(token=bot_token)
            text = f"🎯 **Quest completed!**\n\n{name}\n\nClaim your reward in Game Center → Quests!"
            msg = await bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")
            await asyncio.sleep(5)
            await bot.delete_message(chat_id=user_id, message_id=msg.message_id)
    except Exception as e:
        logging.error(f"Error notifying quest completion: {e}")
            
# ==================== ВОПРОСЫ ДЛЯ РУЧНОГО ФАМБЛА ====================

async def fetch_fumble_questions() -> List[Dict]:
    """Загружает все активные вопросы с вариантами из БД"""
    try:
        questions = supabase.table("fumble_questions").select("*").eq("is_active", True).execute().data
        for q in questions:
            q["options"] = supabase.table("fumble_options").select("*").eq("question_id", q["id"]).order("sort_order").execute().data
        return questions
    except Exception as e:
        logging.error(f"Failed to fetch fumble questions: {e}")
        return []

async def check_and_award_achievements(user_id: int, action: str, value: Any = None):
    """
    Проверяет и выдаёт ачивки пользователю.
    action: 'fumble', 'signal', 'price', 'wallet', 'streak', 'portfolio', 'referral', 'rare_signal', 'leaderboard'
    """
    
    ACHIEVEMENTS = {
        "first_fumble": {
            "name": {"en": "First Fumble", "ru": "Первый фамбл", "es": "Primer Fumble", "zh": "首次失误"},
            "reward": 1,
            "condition": lambda stats, user: stats.get("count", 0) >= 1
        },
        "silver_loser": {
            "name": {"en": "Silver Loser", "ru": "Серебряный лузер", "es": "Perdedor Plateado", "zh": "白银输家"},
            "reward": 2,
            "condition": lambda stats, user: stats.get("count", 0) >= 10
        },
        "gold_loser": {
            "name": {"en": "Gold Loser", "ru": "Золотой лузер", "es": "Perdedor Dorado", "zh": "黄金输家"},
            "reward": 5,
            "condition": lambda stats, user: stats.get("count", 0) >= 50
        },
        "platinum_loser": {
            "name": {"en": "Platinum Loser", "ru": "Платиновый лузер", "es": "Perdedor Platino", "zh": "铂金输家"},
            "reward": 10,
            "condition": lambda stats, user: stats.get("count", 0) >= 100
        },
        "signal_master": {
            "name": {"en": "Signal Master", "ru": "Мастер сигналов", "es": "Maestro de Señales", "zh": "信号大师"},
            "reward": 3,
            "condition": lambda stats, user: user.get("signal_clicks", 0) >= 50
        },
        "paranoid": {
            "name": {"en": "Paranoid", "ru": "Параноик", "es": "Paranoico", "zh": "偏执狂"},
            "reward": 2,
            "condition": lambda stats, user: user.get("price_checks", 0) >= 30
        },
        "hell_holder": {
            "name": {"en": "Hell Holder", "ru": "Адский холдер", "es": "Holder Infernal", "zh": "地狱持有者"},
            "reward": 1,
            "condition": lambda stats, user: user.get("wallet_address") is not None
        },
        "masochist": {
            "name": {"en": "Masochist", "ru": "Мазохист", "es": "Masoquista", "zh": "受虐狂"},
            "reward": 3,
            "condition": lambda stats, user: user.get("streak_days", 0) >= 7
        },
        "crypto_archaeologist": {
            "name": {"en": "Crypto Archaeologist", "ru": "Крипто-археолог", "es": "Arqueólogo Cripto", "zh": "加密考古学家"},
            "reward": 2,
            "condition": lambda stats, user: user.get("portfolio_views", 0) >= 10
        },
        "referral_baron": {
            "name": {"en": "Referral Baron", "ru": "Реферальный барон", "es": "Barón de Referidos", "zh": "推荐男爵"},
            "reward": 5,
            "condition": lambda stats, user: user.get("referral_count", 0) >= 5
        },
        "agent_victim": {
            "name": {"en": "Agent's Victim", "ru": "Жертва агента", "es": "Víctima del Agente", "zh": "特工受害者"},
            "reward": 3,
            "condition": lambda stats, user: user.get("rare_phrases", 0) >= 5
        },
        "king_of_bottom": {
            "name": {"en": "King of the Bottom", "ru": "Король дна", "es": "Rey del Fondo", "zh": "底部之王"},
            "reward": 5,
            "condition": lambda stats, user: False
        },
        "signal_legend": {
            "name": {"en": "Signal Legend", "ru": "Легенда сигналов", "es": "Leyenda de Señales", "zh": "信号传奇"},
            "reward": 5,
            "condition": lambda stats, user: user.get("signal_clicks", 0) >= 100
        },
        "godless": {
            "name": {"en": "Godless", "ru": "Безбожник", "es": "Impío", "zh": "无神论者"},
            "reward": 10,
            "condition": lambda stats, user: user.get("streak_days", 0) >= 30 or user.get("max_streak", 0) >= 30
        },
        "liquidity_sponsor": {
            "name": {"en": "Liquidity Sponsor", "ru": "Спонсор ликвидности", "es": "Patrocinador de Liquidez", "zh": "流动性赞助商"},
            "reward": 10,
            "condition": lambda stats, user: user.get("total_loss_usd", 0) >= 100
        },
        "legend_of_shame": {
            "name": {"en": "Legend of Shame", "ru": "Легенда позора", "es": "Leyenda de la Vergüenza", "zh": "耻辱传奇"},
            "reward": 20,
            "condition": lambda stats, user: False
        },
    }
    
    try:
        user = await get_user(user_id)
        if not user:
            return
        
        stats = await get_user_stats(user_id) or {}
        
        updates = {}
        if action == "signal":
            updates["signal_clicks"] = user.get("signal_clicks", 0) + 1
        elif action == "price":
            updates["price_checks"] = user.get("price_checks", 0) + 1
        elif action == "portfolio":
            updates["portfolio_views"] = user.get("portfolio_views", 0) + 1
        elif action == "rare_signal":
            updates["rare_phrases"] = user.get("rare_phrases", 0) + 1
        elif action == "referral":
            user["referral_count"] = await get_referrals_count(user_id)
        
        if updates:
            supabase.table("user_stats").update(updates).eq("user_id", user_id).execute()
            for k, v in updates.items():
                user[k] = v
        
        earned = await get_user_achievements(user_id)
        earned_keys = [a["achievement_key"] for a in earned]
        
        for key, ach in ACHIEVEMENTS.items():
            if key in earned_keys:
                continue
            if ach["condition"](stats, user):
                await save_achievement(user_id, key)
                
                stats_row = supabase.table("user_stats").select("total_score").eq("user_id", user_id).execute()
                if stats_row.data:
                    current = stats_row.data[0].get("total_score", 0)
                    supabase.table("user_stats").update({"total_score": current + ach["reward"]}).eq("user_id", user_id).execute()
                else:
                    supabase.table("user_stats").insert({"user_id": user_id, "total_score": ach["reward"]}).execute()
                
                lang = await get_language(user_id)
                name = ach["name"].get(lang, ach["name"]["en"])
                
                import telegram
                bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
                if bot_token:
                    bot = telegram.Bot(token=bot_token)
                    text = get_text(lang, "achievement_unlocked").format(name, ach["reward"])
                    try:
                        msg = await bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")
                        await asyncio.sleep(5)
                        await bot.delete_message(chat_id=user_id, message_id=msg.message_id)
                    except Exception:
                        pass
                        
    except Exception as e:
        logging.error(f"Error in check_and_award_achievements: {e}")