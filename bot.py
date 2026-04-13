import os
import random
import logging
import asyncio
import aiohttp
import re
import json
import threading
from datetime import datetime, date, timedelta, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from io import BytesIO
from typing import Optional, Tuple, List, Dict, Any

from PIL import Image, ImageDraw, ImageFont, ImageColor
import qrcode

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters, PollAnswerHandler, ContextTypes, CallbackContext
)
from telegram.constants import ParseMode

# Импорт функций работы с Supabase
from supabase_client import (
    init_supabase,
    get_user, create_user, update_user, delete_user,
    get_language, set_language,
    save_fumble, get_user_stats, get_leaderboard, get_leaderboard_count,
    subscribe_user, unsubscribe_user, is_subscribed, get_all_subscribed_users,
    save_wallet_address, get_wallet_address, delete_wallet_address,
    update_streak, get_streak_info,
    save_achievement, get_user_achievements,
    create_referral, get_referrals_count,
    save_signal_history, get_signal_history,
    get_fumble_history, # <-- Убрали save_fumble_history
    log_certificate_request,
    check_and_award_achievements,
    generate_daily_quests_for_user,
    update_quest_progress,
    claim_quest_reward,
    get_user_active_quests,
    get_user_completed_quests,
    give_referral_bonus,
    get_portfolio_roast,
    send_signal_of_the_day,
    send_auto_signals,
    get_all_achievements,
    check_signal_fumble_bonus,
    fetch_fumble_questions,
    send_weekly_leaderboard,
    save_menu_id,
    get_menu_id,
    check_and_update_limits,
    log_error
)
    
from texts import TEXTS, get_text, add_hooks
from twitter_poster import start_scheduler  # опционально

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

cached_fumble_questions = []

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set")

TOKEN_ADDRESS = os.getenv("TOKEN_ADDRESS", "")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY", "")
HEADERS = {"User-Agent": "Mozilla/5.0"}
SITE_URL = "https://binty.xyz"          # замените на актуальный
CHAT_URL = "https://t.me/bintychat"     # замените на актуальный

# Кэш для цены
price_cache = {"price": None, "change": 0, "timestamp": 0}
CACHE_DURATION = 300

# Хранилище для удаления предыдущих сообщений
MAX_STORAGE = 1000
last_responses = {}
menu_message_ids = {}
user_request_times = {}
user_fumble_state = {}  # {user_id: {"step": 1, "answers": []}}

STICKERS = {"regular": [], "gif": []}
MEMES = ["https://i.imgflip.com/2kbnrp.jpg", "https://i.imgflip.com/1bij.jpg", "https://i.imgflip.com/26am.jpg"]

def is_valid_solana_address(address: str) -> bool:
    return bool(re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', address))

def get_button_text(lang: str, key: str) -> str:
    return TEXTS[lang]["buttons"].get(key, key)

# ==================== МЕНЮ (BINTY) ====================
async def get_main_menu(user_id: int, lang: str) -> InlineKeyboardMarkup:
    """Генерирует главное меню с актуальным статусом подписки"""
    t = TEXTS[lang]["buttons"]
    
    # Проверяем статус подписки
    is_sub = await is_subscribed(user_id)
    subscribe_text = t["unsubscribe"] if is_sub else t["subscribe"]
    subscribe_callback = "unsubscribe" if is_sub else "subscribe"
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["signal"], callback_data="signal"),
         InlineKeyboardButton(t["fumble"], callback_data="fumble")],
        [InlineKeyboardButton(t["portfolio"], callback_data="portfolio"),
         InlineKeyboardButton(t["price"], callback_data="price")],
        [InlineKeyboardButton(t["holders"], callback_data="holders"),
         InlineKeyboardButton(t["balance"], callback_data="balance")],
        [InlineKeyboardButton(t["leaderboard"], callback_data="leaderboard"),
         InlineKeyboardButton(t["meme"], callback_data="meme")],
        [InlineKeyboardButton(subscribe_text, callback_data=subscribe_callback)],
        [InlineKeyboardButton(t["my_stats"], callback_data="my_stats"),
         InlineKeyboardButton(t["game_center"], callback_data="game_center")],
        [InlineKeyboardButton(t["language"], callback_data="language"),
         InlineKeyboardButton(t["help"], callback_data="help")],
        [InlineKeyboardButton(t["buy"], url=f"https://pump.fun/coin/{TOKEN_ADDRESS}"),
         InlineKeyboardButton(t["site"], url=SITE_URL),
         InlineKeyboardButton(t["chat"], url=CHAT_URL),]
    ])

def get_game_center_menu(lang: str) -> InlineKeyboardMarkup:
    t = TEXTS[lang]["buttons"]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["achievements"], callback_data="achievements"),
         InlineKeyboardButton(t["certificate"], callback_data="certificate")],
        [InlineKeyboardButton(t["suffering_calendar"], callback_data="suffering_calendar"),
         InlineKeyboardButton(t["quests"], callback_data="quests")],
        [InlineKeyboardButton(t["manual_fumble"], callback_data="manual_fumble")],
        [InlineKeyboardButton(t["sticker"], callback_data="sticker"),
         InlineKeyboardButton(t["referrals"], callback_data="referrals")],
        [InlineKeyboardButton("↩️t["back_to_menu"], callback_data="back_to_menu")]
    ])

def get_my_stats_menu(lang: str) -> InlineKeyboardMarkup:
    t = TEXTS[lang]["buttons"]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["signal_history"], callback_data="signal_history"),
         InlineKeyboardButton(t["fumble_history"], callback_data="fumble_history")],
        [InlineKeyboardButton("📜 " + get_text(lang, "my_certificates"), callback_data="my_certificates")],
        [InlineKeyboardButton("t["back_to_menu"], callback_data="back_to_menu")]
    ])

# ==================== ПРИВЕТСТВИЯ ====================
WELCOME_NEW = {
    "en": [
        "Oh, a new victim. You sure you want this? Don't say I didn't warn you. 🤡",
        "Another loser who thinks he's special. Spoiler: you're not. Here are the buttons.",
        "Welcome. Your portfolio is already down while you were reading this. You're welcome.",
        "Fresh meat. Ready to lose some money? Let's go. 📉",
        "I was hoping for a smarter one. But you'll do. Here's the menu. Try not to cry.",
        "A new challenger appears. Your first loss is free. The rest will cost you. 💀"
    ],
    "ru": [
        "О, новая жертва. Ты уверен, что хочешь этого? Не говори, что я не предупреждал. 🤡",
        "Ещё один лузер, который думает, что он особенный. Спойлер: нет. Держи кнопки.",
        "Добро пожаловать. Твой портфель уже упал, пока ты это читал. Не благодари.",
        "Свежее мясо. Готов потерять деньги? Погнали. 📉",
        "Я надеялся на более умного. Но ты сойдёшь. Вот меню. Старайся не плакать.",
        "Новый боец. Первый проигрыш — за счёт заведения. Остальные — за твой счёт. 💀"
    ],
    "es": [
        "Oh, una nueva víctima. ¿Seguro que quieres esto? No digas que no te avisé. 🤡",
        "Otro perdedor que cree que es especial. Spoiler: no lo eres. Aquí tienes los botones.",
        "Bienvenido. Tu cartera ya está cayendo mientras leías esto. De nada.",
        "Carne fresca. ¿Listo para perder dinero? Vamos. 📉",
        "Esperaba alguien más inteligente. Pero tú sirves. Aquí está el menú. Intenta no llorar.",
        "Un nuevo contendiente. Tu primera pérdida es gratis. El resto te costará. 💀"
    ],
    "zh": [
        "哦，新的受害者。你确定你想要这个？别说我没警告你。🤡",
        "另一个觉得自己很特别的失败者。剧透：你不是。拿着按钮。",
        "欢迎。在你读这段话的时候，你的投资组合已经在下跌了。不客气。",
        "新鲜血液。准备好亏钱了吗？走吧。📉",
        "我本以为会遇到更聪明的人。但你也行。这是菜单。尽量别哭。",
        "新挑战者。你的第一次亏损是免费的。剩下的会让你付出代价。💀"
    ]
}

WELCOME_OLD = {
    "en": [
        "Oh, you again. Ready to lose some more? Here are your buttons. 📉",
        "Back for more pain? I respect the stupidity. Here's the menu.",
        "You again? I thought you'd learned. You didn't. Buttons are waiting.",
        "Welcome back. Your portfolio is still down. Nothing changed. Here's the menu."
    ],
    "ru": [
        "О, опять ты. Готов слить ещё немного? Держи кнопки. 📉",
        "Снова за болью? Я уважаю тупость. Держи меню.",
        "Опять ты? Я думал, ты научился. Не научился. Кнопки ждут.",
        "С возвращением. Твой портфель всё ещё в минусе. Ничего не изменилось. Держи меню."
    ],
    "es": [
        "Oh, otra vez tú. ¿Listo para perder un poco más? Aquí tienes los botones. 📉",
        "¿De vuelta por más dolor? Respeto la estupidez. Aquí está el menú.",
        "¿Otra vez tú? Pensé que habías aprendido. No lo hiciste. Los botones te esperan.",
        "Bienvenido de nuevo. Tu cartera sigue en rojo. Nada ha cambiado. Aquí está el menú."
    ],
    "zh": [
        "哦，又是你。准备好再亏一点了吗？拿着按钮。📉",
        "又来找痛苦了？我尊重你的愚蠢。这是菜单。",
        "又是你？我以为你已经吸取教训了。你没有。按钮在等着你。",
        "欢迎回来。你的投资组合仍然在亏损。什么都没变。这是菜单。"
    ]
}

def get_welcome(lang: str, is_new: bool) -> str:
    pool = WELCOME_NEW.get(lang, WELCOME_NEW["en"]) if is_new else WELCOME_OLD.get(lang, WELCOME_OLD["en"])
    return random.choice(pool)
    
    # ==================== API ФУНКЦИИ ====================
async def get_price() -> Tuple[Optional[float], float]:
    global price_cache
    now = datetime.now().timestamp()
    if price_cache["timestamp"] and now - price_cache["timestamp"] < CACHE_DURATION:
        return price_cache["price"], price_cache["change"]
    if not TOKEN_ADDRESS:
        return None, 0
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.dexscreener.com/latest/dex/token/{TOKEN_ADDRESS}", headers=HEADERS) as resp:
                data = await resp.json()
                pairs = data.get("pairs", [])
                if not pairs:
                    return None, 0
                price = float(pairs[0].get("priceUsd", 0))
                change = pairs[0].get("priceChange", {}).get("h24", 0)
                price_cache = {"price": price, "change": change, "timestamp": now}
                return price, change
    except Exception as e:
        logging.error(f"Failed to fetch price: {e}")
        return None, 0

async def get_holders() -> Optional[int]:
    if not TOKEN_ADDRESS:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://public-api.solscan.io/token/holders?tokenAddress={TOKEN_ADDRESS}", headers=HEADERS) as resp:
                data = await resp.json()
                if isinstance(data, list):
                    return len(data)
                elif isinstance(data, dict):
                    return data.get("total")
                return None
    except Exception as e:
        logging.error(f"Failed to fetch holders: {e}")
        return None

async def get_wallet_balance(address: str) -> Optional[Tuple[float, float]]:
    if not TOKEN_ADDRESS:
        return None
    try:
        url = f"https://public-api.solscan.io/account/tokens?account={address}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS) as resp:
                data = await resp.json()
                for token in data:
                    if token.get("tokenAddress") == TOKEN_ADDRESS:
                        amount = int(token.get("amount", 0)) / 10 ** token.get("decimals", 9)
                        price, _ = await get_price()
                        return amount, amount * (price or 0)
                return 0.0, 0.0
    except Exception as e:
        logging.error(f"Failed to fetch wallet balance for {address}: {e}")
        return None

async def get_last_swap_transaction(wallet: str) -> Optional[Dict[str, Any]]:
    """Получает последнюю SWAP транзакцию через Helius (или Solscan fallback)"""
    if HELIUS_API_KEY:
        url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions?api-key={HELIUS_API_KEY}&limit=5"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        txs = await resp.json()
                        for tx in txs:
                            if tx.get("type") == "SWAP":
                                return tx
        except Exception as e:
            logging.error(f"Helius error: {e}")

    # Fallback на Solscan (менее детально, но бесплатно)
    url = f"https://public-api.solscan.io/account/transactions?account={wallet}&limit=10"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS) as resp:
            data = await resp.json()
            for tx in data:
                # Solscan не даёт тип явно, ищем по полям
                if "swap" in str(tx).lower():
                    return tx
    return None

async def calculate_fumble_from_tx(tx: Dict[str, Any], wallet: str, lang: str = "en") -> Tuple[int, str, Dict[str, Any]]:
    """
    Парсит транзакцию из Helius и вычисляет фамбл-счёт.
    Возвращает: (score, reason, details)
    """
    details = {}
    
    # Тексты причин на всех языках (оставил как было)
    REASONS = {
        "en": {
            "unknown_type": "Can't determine trade type, but it looks bad.",
            "no_transfers": "Can't see what you bought or sold. But I'm sure you messed up.",
            "unclear_direction": "Didn't understand what you bought and what you sold. But you definitely did something.",
            "buy_big_loss": "Bought a token, it dropped {:.1f}%. Entry was ${:.6f}, now ${:.6f}. Loss ${:.2f}. Classic.",
            "buy_medium_loss": "Bought and it dropped {:.1f}%. Entry ${:.6f} → now ${:.6f}. Down ${:.2f}.",
            "buy_small_loss": "Small loss of {:.1f}%. Lost ${:.2f}. Warm-up.",
            "buy_profit": "You're up {:.1f}%? Suspicious. Profit ${:.2f}. I'm disappointed.",
            "sell_big_loss": "Sold at the bottom. Loss {:.1f}%. Got ${:.2f}. Could've been worse... actually no.",
            "sell_medium_loss": "Sold at a loss of {:.1f}%. Got ${:.2f}. Not the best exit.",
            "sell_small_loss": "Sold with small loss {:.1f}%. ${:.2f} in your pocket.",
            "sell_profit": "Sold at a profit {:.1f}%? Lucky. Got ${:.2f}. But I'm watching.",
            "parse_error": "Something broke during analysis. But I'm sure you lost."
        },
        "ru": {
            "unknown_type": "Не могу определить тип сделки, но выглядит плохо.",
            "no_transfers": "Не вижу, что ты купил или продал. Но уверен — что-то пошло не так.",
            "unclear_direction": "Не понял, что ты купил, а что продал. Но ты точно что-то натворил.",
            "buy_big_loss": "Купил токен, он упал на {:.1f}%. Вход был по ${:.6f}, сейчас ${:.6f}. Убыток ${:.2f}. Классика.",
            "buy_medium_loss": "Купил, а оно упало на {:.1f}%. Вход ${:.6f} → сейчас ${:.6f}. Минус ${:.2f}.",
            "buy_small_loss": "Небольшой минус {:.1f}%. Потерял ${:.2f}. Разминка.",
            "buy_profit": "Ты в плюсе на {:.1f}%? Подозрительно. Прибыль ${:.2f}. Я разочарован.",
            "sell_big_loss": "Продал на дне. Убыток {:.1f}%. Получил ${:.2f}. А мог бы...",
            "sell_medium_loss": "Продал в минус {:.1f}%. Выручил ${:.2f}. Не лучший выход.",
            "sell_small_loss": "Продал с небольшим убытком {:.1f}%. ${:.2f} в кармане.",
            "sell_profit": "Продал в плюс {:.1f}%? Везение. Получил ${:.2f}. Но я слежу.",
            "parse_error": "Что-то сломалось при анализе. Но я уверен — ты проиграл."
        },
        "es": {
            "unknown_type": "No puedo determinar el tipo de operación, pero se ve mal.",
            "no_transfers": "No veo qué compraste o vendiste. Pero seguro que la cagaste.",
            "unclear_direction": "No entendí qué compraste y qué vendiste. Pero definitivamente hiciste algo.",
            "buy_big_loss": "Compraste un token, cayó {:.1f}%. Entrada ${:.6f}, ahora ${:.6f}. Pérdida ${:.2f}. Clásico.",
            "buy_medium_loss": "Compraste y cayó {:.1f}%. Entrada ${:.6f} → ahora ${:.6f}. Abajo ${:.2f}.",
            "buy_small_loss": "Pequeña pérdida de {:.1f}%. Perdiste ${:.2f}. Calentamiento.",
            "buy_profit": "¿Estás arriba {:.1f}%? Sospechoso. Ganancia ${:.2f}. Estoy decepcionado.",
            "sell_big_loss": "Vendiste en el fondo. Pérdida {:.1f}%. Recibiste ${:.2f}. Podría ser peor... bueno no.",
            "sell_medium_loss": "Vendiste con pérdida de {:.1f}%. Recibiste ${:.2f}. No es la mejor salida.",
            "sell_small_loss": "Vendiste con pequeña pérdida {:.1f}%. ${:.2f} en tu bolsillo.",
            "sell_profit": "¿Vendiste con ganancia {:.1f}%? Suerte. Recibiste ${:.2f}. Pero te vigilo.",
            "parse_error": "Algo se rompió durante el análisis. Pero seguro que perdiste."
        },
        "zh": {
            "unknown_type": "无法确定交易类型，但看起来很糟糕。",
            "no_transfers": "看不到你买卖了什么。但我确定你搞砸了。",
            "unclear_direction": "没搞懂你买了什么卖了什么。但你肯定做了什么。",
            "buy_big_loss": "买入代币，跌了{:.1f}%。入场${:.6f}，现在${:.6f}。亏损${:.2f}。经典。",
            "buy_medium_loss": "买入后跌了{:.1f}%。入场${:.6f} → 现在${:.6f}。亏${:.2f}。",
            "buy_small_loss": "小额亏损{:.1f}%。亏了${:.2f}。热身而已。",
            "buy_profit": "你盈利{:.1f}%？可疑。利润${:.2f}。我很失望。",
            "sell_big_loss": "卖在底部。亏损{:.1f}%。得到${:.2f}。本来可以...算了。",
            "sell_medium_loss": "亏损{:.1f}%卖出。拿到${:.2f}。不是最好的退出。",
            "sell_small_loss": "小额亏损{:.1f}%卖出。${:.2f}进口袋。",
            "sell_profit": "盈利{:.1f}%卖出？走运。拿到${:.2f}。但我在看着。",
            "parse_error": "分析时出错了。但我确定你亏了。"
        }
    }
    
    r = REASONS.get(lang, REASONS["en"])
    
    try:
        if tx.get("type") != "SWAP":
            return random.randint(5, 8), r["unknown_type"], {}
        
        token_transfers = tx.get("tokenTransfers", [])
        if not token_transfers:
            return random.randint(5, 8), r["no_transfers"], {}
        
        sent = None
        received = None
        
        for transfer in token_transfers:
            from_user = transfer.get("fromUserAccount", "")
            to_user = transfer.get("toUserAccount", "")
            mint = transfer.get("mint", "")
            amount = float(transfer.get("tokenAmount", 0))
            
            if from_user == wallet:
                sent = {"mint": mint, "amount": amount}
            elif to_user == wallet:
                received = {"mint": mint, "amount": amount}
        
        if not sent or not received:
            return random.randint(5, 8), r["unclear_direction"], {}
        
        SOL_MINT = "So11111111111111111111111111111111111111112"
        USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        
        is_buy = sent["mint"] in [SOL_MINT, USDC_MINT]
        
        # --- ИСПРАВЛЕННАЯ ЧАСТЬ (НАЧАЛО) ---
        # Мы выносим функцию получения цены, но вызываем её через await
        
        async def get_token_price(mint: str) -> float:
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
                    async with session.get(url, headers=HEADERS) as resp:
                        data = await resp.json()
                        pairs = data.get("pairs", [])
                        if pairs:
                            return float(pairs[0].get("priceUsd", 0))
            except:
                pass
            return 0.0
        
        # УБРАЛИ loop = asyncio.new_event_loop()
        # УБРАЛИ loop.run_until_complete
        
        if is_buy:
            bought_mint = received["mint"]
            bought_amount = received["amount"]
            spent_amount = sent["amount"]
            spent_mint = sent["mint"]
            
            # Используем await напрямую
            current_price = await get_token_price(bought_mint)
            
            spent_price = 0
            if spent_mint == SOL_MINT:
                spent_price = await get_token_price(SOL_MINT)
            elif spent_mint == USDC_MINT:
                spent_price = 1.0
            else:
                spent_price = await get_token_price(spent_mint)
            
            spent_usd = spent_amount * spent_price if spent_price > 0 else spent_amount * 20
            
            entry_price = spent_usd / bought_amount if bought_amount > 0 else 0
            current_value = bought_amount * current_price
            
            pnl_usd = current_value - spent_usd
            pnl_percent = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
            
            details = {
                "type": "buy",
                "bought_mint": bought_mint,
                "bought_amount": bought_amount,
                "spent_usd": spent_usd,
                "entry_price": entry_price,
                "current_price": current_price,
                "pnl_usd": pnl_usd,
                "pnl_percent": pnl_percent
            }
            
            if pnl_percent <= -30:
                score = random.randint(9, 10)
                reason = r["buy_big_loss"].format(abs(pnl_percent), entry_price, current_price, abs(pnl_usd))
            elif pnl_percent <= -15:
                score = random.randint(7, 8)
                reason = r["buy_medium_loss"].format(abs(pnl_percent), entry_price, current_price, abs(pnl_usd))
            elif pnl_percent < 0:
                score = random.randint(5, 6)
                reason = r["buy_small_loss"].format(abs(pnl_percent), abs(pnl_usd))
            else:
                score = random.randint(0, 2)
                reason = r["buy_profit"].format(pnl_percent, pnl_usd)
                
        else:
            sold_mint = sent["mint"]
            sold_amount = sent["amount"]
            received_mint = received["mint"]
            received_amount = received["amount"]
            
            received_price = 0
            if received_mint == SOL_MINT:
                received_price = await get_token_price(SOL_MINT)
            elif received_mint == USDC_MINT:
                received_price = 1.0
            else:
                received_price = await get_token_price(received_mint)
                
            received_usd = received_amount * received_price if received_price > 0 else received_amount
            
            current_price = await get_token_price(sold_mint)
            estimated_entry = current_price * random.uniform(0.7, 1.5)
            
            pnl_percent = ((received_usd / sold_amount) - estimated_entry) / estimated_entry * 100 if estimated_entry > 0 else 0
            pnl_usd = received_usd - (sold_amount * estimated_entry)
            
            details = {
                "type": "sell",
                "sold_mint": sold_mint,
                "sold_amount": sold_amount,
                "received_usd": received_usd,
                "current_price": current_price,
                "pnl_usd": pnl_usd,
                "pnl_percent": pnl_percent
            }
            
            if pnl_percent <= -30:
                score = random.randint(9, 10)
                reason = r["sell_big_loss"].format(abs(pnl_percent), received_usd)
            elif pnl_percent <= -15:
                score = random.randint(7, 8)
                reason = r["sell_medium_loss"].format(abs(pnl_percent), received_usd)
            elif pnl_percent < 0:
                score = random.randint(5, 6)
                reason = r["sell_small_loss"].format(abs(pnl_percent), received_usd)
            else:
                score = random.randint(0, 2)
                reason = r["sell_profit"].format(pnl_percent, received_usd)
        
        # УБРАЛИ loop.close()
        
        score = max(0, min(10, score + random.randint(-1, 1)))
        return score, reason, details
        
    except Exception as e:
        logging.error(f"Error parsing transaction: {e}")
        return random.randint(5, 8), r["parse_error"], {}
                
async def get_portfolio_history(address: str, days: int = 7):
    if not address or not TOKEN_ADDRESS:
        return None
    try:
        balance_result = await get_wallet_balance(address)
        if not balance_result:
            return None
        current_amount, current_value = balance_result
        if current_amount == 0:
            return None
        history = []
        base_price, _ = await get_price()
        if not base_price:
            base_price = 0.001
        for i in range(days):
            factor = 1 - (i * random.uniform(0.02, 0.08))
            factor = max(0.3, factor)
            price = base_price * factor
            value = current_amount * price
            history.append({"day": i+1, "value": value})
        return history, current_amount, current_value
    except Exception as e:
        logging.error(f"Failed to get portfolio history: {e}")
        return None

def generate_portfolio_chart_fake():
    width, height = 500, 300
    image = Image.new('RGB', (width, height), color='black')
    draw = ImageDraw.Draw(image)
    points = []
    value = 100
    for i in range(10):
        value -= random.uniform(2, 8)
        if value < 50:
            value = 50 + random.uniform(0, 5)
        x = i * (width // 10)
        y = height - (value / 100) * height
        points.append((x, y))
    for i in range(len(points)-1):
        draw.line([points[i], points[i+1]], fill='red', width=3)
    for point in points:
        draw.ellipse([point[0]-3, point[1]-3, point[0]+3, point[1]+3], fill='white')
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except:
        font = ImageFont.load_default()
    draw.text((10, 10), "BINTY Portfolio (simulated)", fill="white", font=font)
    draw.text((10, height-20), "Time", fill="white", font=font)
    draw.text((width-50, 10), "Value ↓", fill="white", font=font)
    img_bytes = BytesIO()
    image.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    return img_bytes

def generate_portfolio_chart_real(history, current_amount, current_value):
    if not history:
        return generate_portfolio_chart_fake()
    width, height = 500, 300
    image = Image.new('RGB', (width, height), color='black')
    draw = ImageDraw.Draw(image)
    max_value = max([p["value"] for p in history]) if history else 1
    min_value = min([p["value"] for p in history]) if history else 0
    if max_value == min_value:
        max_value = min_value + 1
    points = []
    for i, point in enumerate(history):
        x = i * (width // (len(history)-1 if len(history)>1 else 1))
        y = height - ((point["value"] - min_value) / (max_value - min_value)) * height * 0.8 - 20
        points.append((x, y))
    for i in range(len(points)-1):
        draw.line([points[i], points[i+1]], fill='red', width=3)
    for point in points:
        draw.ellipse([point[0]-3, point[1]-3, point[0]+3, point[1]+3], fill='white')
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except:
        font = ImageFont.load_default()
    draw.text((10, 10), "BINTY Portfolio", fill="white", font=font)
    draw.text((10, height-20), f"Balance: {current_amount:.4f} BINTY", fill="#00ff99", font=font)
    draw.text((width-150, 10), f"Value: ${current_value:.2f}", fill="white", font=font)
    img_bytes = BytesIO()
    image.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    return img_bytes
    
# ==================== СЕРТИФИКАТ ПОЗОРА ====================
def generate_certificate_of_shame(user_id: int, username: str, level_name: str,
                                 total_fumbles: int, avg_score: float,
                                 position: int, lang: str) -> BytesIO:
    # Высокое разрешение
    width, height = 1200, 800
    img = Image.new('RGB', (width, height), color='#0a0f1a')
    draw = ImageDraw.Draw(img)

    # Градиентный фон (тёмно-синий → чёрный)
    for y in range(height):
        r = int(10 + (y / height) * 20)
        g = int(15 + (y / height) * 25)
        b = int(26 + (y / height) * 30)
        draw.rectangle([(0, y), (width, y)], fill=(r, g, b))

    # Золотая двойная рамка с орнаментом
    draw.rectangle([30, 30, width-30, height-30], outline='#d4af37', width=6)
    draw.rectangle([42, 42, width-42, height-42], outline='#d4af37', width=2)
    
    # Угловые узоры
    for x, y in [(50, 50), (width-50, 50), (50, height-50), (width-50, height-50)]:
        draw.ellipse([x-10, y-10, x+10, y+10], fill='#d4af37')
        draw.ellipse([x-6, y-6, x+6, y+6], fill='#0a0f1a')

    # Шрифты (используем стандартные, но с увеличенным размером)
    try:
        font_title = ImageFont.truetype("arial.ttf", 72)
        font_name = ImageFont.truetype("arial.ttf", 48)
        font_text = ImageFont.truetype("arial.ttf", 32)
        font_small = ImageFont.truetype("arial.ttf", 24)
    except:
        font_title = ImageFont.load_default()
        font_name = ImageFont.load_default()
        font_text = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Заголовок
    title = TEXTS[lang].get("certificate_title", "CERTIFICATE OF SHAME")
    draw.text((width//2, 100), title, fill='#d4af37', font=font_title, anchor='mm')
    draw.text((width//2, 170), "BINTY", fill='#ffffff', font=font_name, anchor='mm')

    # Линия-разделитель
    draw.line([(150, 210), (width-150, 210)], fill='#d4af37', width=3)

    # Имя получателя
    draw.text((width//2, 280), "This certificate is awarded to", fill='#aaaaaa', font=font_small, anchor='mm')
    display_name = username or f"User {user_id}"
    draw.text((width//2, 350), display_name, fill='#ffffff', font=font_name, anchor='mm')

    draw.line([(200, 400), (width-200, 400)], fill='#d4af37', width=2)

    # Статистика (две колонки)
    y = 470
    col1_x = 250
    col2_x = 700

    draw.text((col1_x, y), "Level:", fill='#d4af37', font=font_text)
    draw.text((col1_x + 150, y), level_name, fill='#ffffff', font=font_text)

    draw.text((col1_x, y + 60), "Total Fumbles:", fill='#d4af37', font=font_text)
    draw.text((col1_x + 250, y + 60), str(total_fumbles), fill='#ffffff', font=font_text)

    draw.text((col2_x, y), "Avg Score:", fill='#d4af37', font=font_text)
    draw.text((col2_x + 180, y), f"{avg_score:.1f}", fill='#ffffff', font=font_text)

    draw.text((col2_x, y + 60), "Position:", fill='#d4af37', font=font_text)
    draw.text((col2_x + 180, y + 60), f"#{position}", fill='#ffffff', font=font_text)

    # Дата выдачи
    y = 620
    draw.text((width//2, y), f"Issued: {datetime.now().strftime('%Y-%m-%d')}", fill='#aaaaaa', font=font_small, anchor='mm')

    # QR-код (справа внизу)
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(f"https://t.me/BintyAgentBot?start=ref_{user_id}")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    qr_img = qr_img.resize((180, 180))
    img.paste(qr_img, (width-250, height-250))

    draw.text((width-160, height-60), "Scan to join", fill='#888888', font=font_small, anchor='mm')

    # Нижняя подпись
    draw.text((width//2, height-60), "BINTY — Financial Enemy #1", fill='#d4af37', font=font_small, anchor='mm')

    # Печать (из файла Untitled.png)
    try:
        seal = Image.open("Untitled.png").convert("RGBA")
        seal = seal.resize((200, 200))
        img.paste(seal, (width//2 - 100, 480), seal)
    except:
        pass  # если файл не найден — просто без печати

    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    return img_bytes

    
    # ==================== УРОВНИ ====================
LEVELS = {
    "en": ["Paper Hands", "Binty Rookie", "Exit Liquidity", "Market Destroyer", "Legendary Rekt"],
    "ru": ["Бумажные руки", "Новичок Бинти", "Ликвидность", "Разрушитель рынка", "Легендарный рект"],
    "es": ["Manos de papel", "Novato Binty", "Liquidez", "Destructor de mercado", "Rekt legendario"],
    "zh": ["纸手", "Binty新手", "流动性", "市场摧毁者", "传奇爆仓"]
}

def get_level_name(level: int, lang: str) -> str:
    levels = LEVELS.get(lang, LEVELS["en"])
    idx = min(level - 1, len(levels)-1) if level > 0 else 0
    return levels[idx]

def get_level(avg_score: float) -> int:
    if avg_score >= 9: return 5
    if avg_score >= 7: return 4
    if avg_score >= 5: return 3
    if avg_score >= 3: return 2
    return 1

async def get_user_position(user_id: int) -> int:
    # Теперь через Supabase
    from supabase_client import supabase
    try:
        res = supabase.rpc('get_user_leaderboard_position', {'p_user_id': user_id}).execute()
        return res.data if res.data else 0
    except Exception as e:
        logging.error(f"Position error: {e}")
        return 0

def get_leaderboard_title(position: int, lang: str) -> str:
    titles = TEXTS[lang].get("leaderboard_titles", {})
    return titles.get(str(position), "")

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
async def check_rate_limit(user_id: int) -> bool:
    now = datetime.now().timestamp()
    if user_id in user_request_times:
        times = user_request_times[user_id]
        times = [t for t in times if now - t < 60]
        if len(times) >= 10:
            return False
        times.append(now)
        user_request_times[user_id] = times
    else:
        user_request_times[user_id] = [now]
    return True

def clean_storage():
    global last_responses, menu_message_ids
    if len(last_responses) > MAX_STORAGE:
        items = list(last_responses.items())
        to_remove = items[:MAX_STORAGE // 2]
        for user_id, _ in to_remove:
            del last_responses[user_id]
    if len(menu_message_ids) > MAX_STORAGE:
        items = list(menu_message_ids.items())
        to_remove = items[:MAX_STORAGE // 2]
        for user_id, _ in to_remove:
            del menu_message_ids[user_id]

async def delete_previous_and_send(chat_id: int, user_id: int, text: str,
                                   context: ContextTypes.DEFAULT_TYPE,
                                   reply_markup=None, parse_mode=None,
                                   photo=None):
    global last_responses
    
    # Удаляем предыдущее контентное сообщение
    if user_id in last_responses:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_responses[user_id])
        except Exception as e:
            logging.error(f"Failed to delete content message for {user_id}: {e}")
    
    # Отправляем новое
    if photo:
        msg = await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=text,
                                           reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        msg = await context.bot.send_message(chat_id=chat_id, text=text,
                                             reply_markup=reply_markup, parse_mode=parse_mode)
    
    # Сохраняем ID контентного сообщения
    last_responses[user_id] = msg.message_id
    clean_storage()
    return msg
    
async def send_with_pause(chat_id: int, user_id: int, first_text: str,
                          second_text: str, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=chat_id, text=first_text)
    await asyncio.sleep(2)
    lang = await get_language(user_id)
    final_text = add_hooks(lang, second_text)
    await delete_previous_and_send(chat_id, user_id, final_text, context)

async def update_menu(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE, lang: str = None):
    """Обновляет главное меню, сохраняя ID в БД для перезапусков"""
    global menu_message_ids, last_responses
    
    if lang is None:
        lang = await get_language(user_id)
    
    # Удаляем контентное сообщение, если есть
    if user_id in last_responses:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_responses[user_id])
            del last_responses[user_id]
        except:
            pass
    
    menu_text = TEXTS[lang].get("menu_title", "📋 BINTY Menu")
    menu_markup = await get_main_menu(user_id, lang)
    
    # 1. Ищем ID сообщения меню: сначала в памяти (быстро)
    msg_id = menu_message_ids.get(user_id)
    
    # 2. Если в памяти нет (бот перезагружался), ищем в БД
    if not msg_id:
        msg_id = await get_menu_id(user_id)
    
    # 3. Пытаемся отредактировать сообщение
    if msg_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=menu_text,
                reply_markup=menu_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            # Сохраняем ID в кэш памяти, чтобы下次 не дергать БД
            menu_message_ids[user_id] = msg_id
            return
        except Exception as e:
            logging.warning(f"Failed to edit menu {msg_id} for {user_id}: {e}")
            # Если ошибка (сообщение удалено), код пойдет дальше и создаст новое
    
    # 4. Если отредактировать не вышло или ID не найден — шлем новое сообщение
    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=menu_text,
        reply_markup=menu_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # 5. Сохраняем новый ID и в память, и в БД
    menu_message_ids[user_id] = msg.message_id
    await save_menu_id(user_id, msg.message_id)
            
# ==================== ОСНОВНЫЕ ОБРАБОТЧИКИ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    lang = await get_language(user_id)
    
        # Добавляем дисклеймер для новых
    if is_new:
        disclaimer = "\n\n⚠️ *Важно: Я финансовый враг. Мои советы ведут к разорению. Нажимая кнопки, ты соглашаешься с тем, что у тебя нет шансов.*"
        welcome_text += disclaimer
    
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
    
    # Реферальная система
    if context.args and context.args[0].startswith('ref_'):
        try:
            referrer_id = int(context.args[0][4:])
            if referrer_id != user_id:
                await create_referral(referrer_id, user_id)
                await check_and_award_achievements(referrer_id, 'referral')
        except:
            pass

    user = await get_user(user_id)
    is_new = user is None
    if is_new:
        await create_user(user_id, update.effective_user.username,
                          update.effective_user.first_name, lang)
    else:
        await update_user(user_id, last_active=datetime.now())

    welcome_text = get_welcome(lang, is_new)
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
    
    stats = await get_user_stats(user_id)
    if stats:
        level = get_level(stats["average"])
        level_name = get_level_name(level, lang)
        stat_text = f"📊 **Your stats:** Level {level}/5 | Avg: {stats['average']:.1f} | Fumbles: {stats['count']}"
    else:
        stat_text = "📊 **Your stats:** New fumbler! Ready to lose money?"
    await update.message.reply_text(stat_text, parse_mode=ParseMode.MARKDOWN)
    
    msg = await update.message.reply_text(
        TEXTS[lang].get("menu_title", "📋 BINTY Menu"),
        reply_markup=await get_main_menu(user_id, lang),
        parse_mode=ParseMode.MARKDOWN
    )
    menu_message_ids[user_id] = msg.message_id
    
    await save_menu_id(user_id, msg.message_id)

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
        # --- НОВОЕ: ПРОВЕРКА ЛИМИТА ---
    limit_check = await check_and_update_limits(user_id, 'signal')
    if not limit_check['allowed']:
        # Если лимит исчерпан, отправляем сообщение и выходим
        await query.answer(limit_check['message'], show_alert=True)
        return
    # ------------------------------
    
    if not await check_rate_limit(user_id):
        await query.message.reply_text(TEXTS[lang].get("rate_limit", "⏳ Too many requests."))
        return
    
    await update_streak(user_id)
    
    await update_quest_progress(user_id, 'signal_count', 1)
    
    # Удаляем предыдущее контентное сообщение
    if user_id in last_responses:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_responses[user_id])
        except:
            pass
    
    pause_text = get_text(lang, "signal_pause")
    pause_msg = await context.bot.send_message(chat_id=chat_id, text=pause_text)
    last_responses[user_id] = pause_msg.message_id
    
    await asyncio.sleep(3)
    
    signal_text = get_text(lang, "signal")
    final_signal = add_hooks(lang, signal_text)
    await pause_msg.edit_text(final_signal, parse_mode=ParseMode.MARKDOWN)
    
    await save_signal_history(user_id, signal_text)
    await check_and_award_achievements(user_id, 'streak')
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        await update_user_title(user_id, update.effective_chat.id, context)
        
async def fumble_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Умный фамбл: анализ реальной транзакции через Helius/Solscan"""
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
        # --- НОВОЕ: ПРОВЕРКА ЛИМИТА ---
    # Умный фамбл (анализ кошелька) можно оставить без лимита или сделать отдельный тип
    # Но для ручного/общего проверим:
    limit_check = await check_and_update_limits(user_id, 'fumble')
    if not limit_check['allowed']:
        await query.answer(limit_check['message'], show_alert=True)
        return
    # ------------------------------
    
    if not await check_rate_limit(user_id):
        await query.message.reply_text(TEXTS[lang].get("rate_limit", "⏳ Too many requests."))
        return
    
    await update_streak(user_id)
    await update_quest_progress(user_id, 'fumble_count', 1)
    
    # Удаляем предыдущий контент
    if user_id in last_responses:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_responses[user_id])
            del last_responses[user_id]
        except:
            pass
    
    wallet = await get_wallet_address(user_id)
    if not wallet:
        # Нет кошелька — редактируем меню
        text = get_text(lang, "no_wallet_for_smart_fumble")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧠 " + get_button_text(lang, "manual_fumble"), callback_data="manual_fumble")],
            [InlineKeyboardButton("↩️ " + get_button_text(lang, "back_to_menu"), callback_data="back_to_menu")]
        ])
        # Редактируем меню
        if user_id in menu_message_ids:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=menu_message_ids[user_id],
                    text=text,
                    reply_markup=kb,
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
                menu_message_ids[user_id] = msg.message_id
        else:
            msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
            menu_message_ids[user_id] = msg.message_id
        return
    
    tx = await get_last_swap_transaction(wallet)
    if not tx:
        # Кошелёк есть, но транзакций нет — редактируем меню
        text = get_text(lang, "no_tx_for_smart_fumble")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧠 " + get_button_text(lang, "manual_fumble"), callback_data="manual_fumble")],
            [InlineKeyboardButton("↩️ " + get_button_text(lang, "back_to_menu"), callback_data="back_to_menu")]
        ])
        if user_id in menu_message_ids:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=menu_message_ids[user_id],
                    text=text,
                    reply_markup=kb,
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
                menu_message_ids[user_id] = msg.message_id
        else:
            msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
            menu_message_ids[user_id] = msg.message_id
        return
    
    # Пытаемся выполнить умный фамбл
    try:
        await update_quest_progress(user_id, 'smart_fumble', 1)
        score, reason, tx_details = await calculate_fumble_from_tx(tx, wallet, lang)
        await save_fumble(user_id, score, type='smart', details=json.dumps(tx_details))
        
        result_text = get_text(lang, "fumble_smart_result", score, reason)
        balance = await get_wallet_balance(wallet)
        if balance:
            amt, val = balance
            result_text += f"\n\n💰 Current BINTY: {amt:.4f} (${val:.2f})"
        
        final_text = add_hooks(lang, result_text)
        msg = await context.bot.send_message(chat_id=chat_id, text=final_text, parse_mode=ParseMode.MARKDOWN)
        last_responses[user_id] = msg.message_id
        await check_and_award_achievements(user_id, 'fumble', score)
        if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
            await update_user_title(user_id, update.effective_chat.id, context)
        logging.info(f"SMART FUMBLE: success for user {user_id}, score={score}")
    except Exception as e:
        logging.error(f"SMART FUMBLE: failed for user {user_id}: {e}", exc_info=True)
        text = get_text(lang, "smart_fumble_error")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧠 " + get_button_text(lang, "manual_fumble"), callback_data="manual_fumble")],
            [InlineKeyboardButton("↩️ " + get_button_text(lang, "back_to_menu"), callback_data="back_to_menu")]
        ])
        if user_id in menu_message_ids:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=menu_message_ids[user_id],
                    text=text,
                    reply_markup=kb,
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
                menu_message_ids[user_id] = msg.message_id
        else:
            msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
            menu_message_ids[user_id] = msg.message_id
        
async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_answer = update.poll_answer
    user_id = poll_answer.user.id
    lang = await get_language(user_id)
    
    if not await check_rate_limit(user_id):
        await context.bot.send_message(chat_id=user_id, text=TEXTS[lang].get("rate_limit", "⏳ Too many requests."))
        return
    
    score = random.randint(0, 10)
    bonus = await check_signal_fumble_bonus(user_id)
    if bonus:
        score = min(10, score + bonus)
    
    await save_fumble(user_id, score, type='manual')
    await update_quest_progress(user_id, 'fumble_count', 1)
    
    result_text = get_text(lang, f"fumble_result_{'high' if score>=7 else 'medium' if score>=4 else 'low'}", score)
    
    wallet = await get_wallet_address(user_id)
    if wallet:
        balance = await get_wallet_balance(wallet)
        if balance:
            amt, val = balance
            result_text += f"\n\n💰 BINTY: {amt:.4f} (${val:.2f})"
    
    final_text = add_hooks(lang, result_text)
    
    # Удаляем предыдущее контентное сообщение (опрос уже удалён, но может быть что-то ещё)
    if user_id in last_responses:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=last_responses[user_id])
        except:
            pass
    
    # Отправляем результат
    msg = await context.bot.send_message(chat_id=user_id, text=final_text, parse_mode=ParseMode.MARKDOWN)
    last_responses[user_id] = msg.message_id
    await check_and_award_achievements(user_id, 'fumble', score)
# Обновляем титул в чате (если бот в группе)
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        await update_user_title(user_id, update.effective_chat.id, context)
  
async def manual_fumble_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
    if not await check_rate_limit(user_id):
        await query.message.reply_text(TEXTS[lang].get("rate_limit", "⏳ Too many requests."))
        return
    
    global cached_fumble_questions
    if not cached_fumble_questions:
        await query.message.reply_text("❌ Вопросы не загружены. Попробуй позже.")
        return
    
    import random
    questions = cached_fumble_questions.copy()
    random.shuffle(questions)
    
    user_fumble_state[user_id] = {
        "q_index": 0,
        "answers": [],
        "score": 0,
        "questions": questions[:5]
    }
    
    await show_fumble_question(user_id, chat_id, lang, context)
      
async def show_fumble_question(user_id: int, chat_id: int, lang: str, context: ContextTypes.DEFAULT_TYPE):
    state = user_fumble_state.get(user_id)
    if not state:
        return
        
    logging.info(f"FUMBLE_FINISH: user={user_id}, answers={len(state['answers'])}")
    
    questions = state["questions"]
    q_index = state["q_index"]
    total = len(questions)
    
    if q_index >= total:
        await finish_manual_fumble(user_id, chat_id, lang, context)
        return
    
    q_data = questions[q_index]
    question_text = q_data[f"question_{lang}"] or q_data["question_en"]
    
    text = f"🎲 **Вопрос {q_index + 1}/{total}**\n\n{question_text}"
    
    buttons = []
    for opt in q_data["options"]:
        option_text = opt[f"option_{lang}"] or opt["option_en"]
        weight = opt["weight"]
        callback = f"fumble_answer_{q_index}_{weight}"
        buttons.append([InlineKeyboardButton(option_text, callback_data=callback)])
    
    buttons.append([InlineKeyboardButton("❌ " + get_text(lang, "cancel_btn"), callback_data="fumble_cancel")])
    keyboard = InlineKeyboardMarkup(buttons)
    
    if user_id in menu_message_ids:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=menu_message_ids[user_id],
                text=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
    else:
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        menu_message_ids[user_id] = msg.message_id
                        
async def fumble_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    lang = await get_language(user_id)
    await query.answer()
    
    data = query.data
    logging.info(f"FUMBLE_ANSWER: user={user_id}, data={data}")
    
    state = user_fumble_state.get(user_id)
    if not state:
        await query.answer("Сессия устарела. Начни заново.", show_alert=True)
        return
    
    # Если квиз уже завершён, игнорируем нажатия
    if state.get("finished"):
        await query.answer("Квиз уже завершён", show_alert=True)
        return
    
    parts = data.split("_")
    if len(parts) < 4:
        await query.answer("Ошибка. Попробуй снова.", show_alert=True)
        return
    
    q_index = int(parts[2])
    weight = parts[3]
    
    # Проверяем, что это ответ на текущий вопрос
    if q_index != state["q_index"]:
        await query.answer("Этот вопрос уже неактуален", show_alert=True)
        return
    
    # Начисляем баллы
    if weight == "high":
        score_add = random.randint(8, 10)
    elif weight == "medium":
        score_add = random.randint(5, 7)
    else:
        score_add = random.randint(2, 4)
    
    state["score"] += score_add
    state["answers"].append({"q_index": q_index, "weight": weight, "score": score_add})
    state["q_index"] += 1
    
    # Если это был последний вопрос, помечаем как завершённый
    if state["q_index"] >= len(state["questions"]):
        state["finished"] = True
    
    user_fumble_state[user_id] = state
    
    await show_fumble_question(user_id, query.message.chat_id, lang, context)
                 
async def finish_manual_fumble(user_id: int, chat_id: int, lang: str, context: ContextTypes.DEFAULT_TYPE):
    state = user_fumble_state.get(user_id)
    if not state:
        return
    
    total_score = state["score"]
    avg_score = min(10, max(0, int(total_score / len(state["answers"]))) if state["answers"] else 5)
    avg_score += random.randint(-1, 1)
    avg_score = min(10, max(0, avg_score))
    
    await save_fumble(user_id, avg_score, type='manual')
    await update_quest_progress(user_id, 'fumble_count', 1)
    await check_and_award_achievements(user_id, 'fumble', avg_score)
    
    if avg_score >= 7:
        result_text = get_text(lang, "fumble_result_high", avg_score)
    elif avg_score >= 4:
        result_text = get_text(lang, "fumble_result_medium", avg_score)
    else:
        result_text = get_text(lang, "fumble_result_low", avg_score)
    
    wallet = await get_wallet_address(user_id)
    if wallet:
        balance = await get_wallet_balance(wallet)
        if balance:
            amt, val = balance
            result_text += f"\n\n💰 BINTY: {amt:.4f} (${val:.2f})"
    
    final_text = add_hooks(lang, result_text)
    
    if user_id in last_responses:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_responses[user_id])
        except:
            pass
    
    msg = await context.bot.send_message(chat_id=chat_id, text=final_text, parse_mode=ParseMode.MARKDOWN)
    last_responses[user_id] = msg.message_id
    
    del user_fumble_state[user_id]
    
    # Даём секунду, чтобы результат точно отобразился перед возвратом в меню
    await asyncio.sleep(1)
    await update_menu(chat_id, user_id, context, lang)
            
async def fumble_cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer("Отменено")
    
    if user_id in user_fumble_state:
        del user_fumble_state[user_id]
    
    await update_menu(chat_id, user_id, context, lang)
                            
async def portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    if not await check_rate_limit(user_id):
        await query.message.reply_text(TEXTS[lang].get("rate_limit", "⏳ Too many requests."))
        return
    address = await get_wallet_address(user_id)
    if not address:
        await delete_previous_and_send(chat_id, user_id, get_text(lang, "portfolio_no_wallet"), context)
        return
    await context.bot.send_chat_action(chat_id=chat_id, action="upload_photo")
    history_data = await get_portfolio_history(address, days=7)
    if history_data:
        history, amount, value = history_data
        chart = generate_portfolio_chart_real(history, amount, value)
        first_val = history[0]["value"] if history else value
        change = ((value - first_val) / first_val * 100) if first_val > 0 else 0
        text = get_text(lang, "portfolio", amount, value, change)
        final_text = add_hooks(lang, text)
        await delete_previous_and_send(chat_id, user_id, final_text, context, photo=chart)
    else:
        chart = generate_portfolio_chart_fake()
        text = get_text(lang, "portfolio", 0, 0, 0)
        final_text = add_hooks(lang, text)
        await delete_previous_and_send(chat_id, user_id, final_text, context, photo=chart)
                
# Остальные обработчики (price, holders, balance, meme, sticker, leaderboard, subscribe/unsubscribe,
# language, help, game_center, my_stats, achievements, certificate, suffering_calendar,
# quests, referrals, signal_history, fumble_history) аналогично добавляются.
# Здесь приведу ключевые новые:

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
    if not await check_rate_limit(user_id):
        await query.message.reply_text(TEXTS[lang].get("rate_limit", "⏳ Too many requests."))
        return
        
    await update_streak(user_id)
    
    await check_and_award_achievements(user_id, 'price')
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    usd, change = await get_price()
    if usd is None:
        await delete_previous_and_send(chat_id, user_id, get_text(lang, "price_unavailable"), context)
        return
    
    emoji = "📈" if change >= 0 else "📉"
    if change >= 5:
        price_text = get_text(lang, "price_up")
    elif change <= -5:
        price_text = get_text(lang, "price_down")
    else:
        price_text = get_text(lang, "price_response", usd, emoji, change)
    
    final_text = add_hooks(lang, price_text)
    await delete_previous_and_send(chat_id, user_id, final_text, context, parse_mode=ParseMode.MARKDOWN)
                
async def holders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
    if not await check_rate_limit(user_id):
        await query.message.reply_text(TEXTS[lang].get("rate_limit", "⏳ Too many requests."))
        return
        
    await update_streak(user_id)
    await check_and_award_achievements(user_id, 'streak')
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        await update_user_title(user_id, update.effective_chat.id, context)

    
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    count = await get_holders()
    
    if count is None:
        await delete_previous_and_send(chat_id, user_id, get_text(lang, "holders_unavailable"), context)
    else:
        text = get_text(lang, "holders", count)
        final_text = add_hooks(lang, text)
        await delete_previous_and_send(chat_id, user_id, final_text, context, parse_mode=ParseMode.MARKDOWN)
                        
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
    if not await check_rate_limit(user_id):
        await query.message.reply_text(TEXTS[lang].get("rate_limit", "⏳ Too many requests."))
        return
    
    await update_streak(user_id)
    await check_and_award_achievements(user_id, 'streak')
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        await update_user_title(user_id, update.effective_chat.id, context)
    
    cancel_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text(lang, "cancel_btn"), callback_data="cancel_balance")]
    ])
    text = get_text(lang, "balance_prompt")
    await delete_previous_and_send(chat_id, user_id, text, context, reply_markup=cancel_kb)
    context.user_data['awaiting_balance'] = True
    
async def cancel_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    context.user_data['awaiting_balance'] = False
    await query.answer()
    
    text = get_text(lang, "balance_cancelled")
    await delete_previous_and_send(chat_id, user_id, text, context)
    
async def handle_balance_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = await get_language(user_id)
    
    if context.user_data.get('awaiting_balance'):
        address = update.message.text.strip()
        if not is_valid_solana_address(address):
            await update.message.reply_text(get_text(lang, "balance_invalid"))
            return
        
        context.user_data['awaiting_balance'] = False
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        result = await get_wallet_balance(address)
        if result is None:
            await update.message.reply_text(get_text(lang, "balance_error"))
        else:
            amount, value = result
            await save_wallet_address(user_id, address)
            await check_and_award_achievements(user_id, 'wallet')
            roast = await get_portfolio_roast(address, lang)
            text = get_text(lang, "balance_response", address, amount, value)
            text += f"\n\n*{roast}*"
            final_text = add_hooks(lang, text)
            await update.message.reply_text(final_text, parse_mode=ParseMode.MARKDOWN)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Заглушка для обычных сообщений
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    lang = await get_language(user_id)
    await delete_previous_and_send(chat_id, user_id, get_text(lang, "unknown"), context)
    
async def meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
    if not await check_rate_limit(user_id):
        await query.message.reply_text(TEXTS[lang].get("rate_limit", "⏳ Too many requests."))
        return
        
    await update_streak(user_id)
    await check_and_award_achievements(user_id, 'streak')
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        await update_user_title(user_id, update.effective_chat.id, context)
    
    await context.bot.send_chat_action(chat_id=chat_id, action="upload_photo")
    url = random.choice(MEMES)
    text = get_text(lang, "meme")
    final_text = add_hooks(lang, text)
    await delete_previous_and_send(chat_id, user_id, final_text, context, photo=url)
        
async def certificate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
    stats = await get_user_stats(user_id)
    if not stats or stats.get("count", 0) == 0:
        await query.message.reply_text(get_text(lang, "no_fumbles_yet"))
        return
    
    await update_streak(user_id)
    await check_and_award_achievements(user_id, 'streak')
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        await update_user_title(user_id, update.effective_chat.id, context)
    
    level = get_level(stats["average"])
    level_name = get_level_name(level, lang)
    position = await get_user_position(user_id)
    username = query.from_user.username or query.from_user.first_name
    
    try:
        img = generate_certificate_of_shame(user_id, username, level_name,
                                            stats["count"], stats["average"],
                                            position, lang)
        await log_certificate_request(user_id)
        
        caption = TEXTS[lang].get("certificate_caption", "Here is your Certificate of Shame.")
        
        if user_id in last_responses:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=last_responses[user_id])
            except:
                pass
        
        msg = await context.bot.send_photo(chat_id=chat_id, photo=img, caption=caption)
        last_responses[user_id] = msg.message_id
        
        await save_certificate(user_id, msg.photo[-1].file_id)
        
    except Exception as e:
        logging.error(f"Certificate error: {e}")
        await query.message.reply_text("Error generating certificate")        
        
async def view_certificate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
    cert_id = int(query.data.replace("view_cert_", ""))
    certificates = await get_user_certificates(user_id)
    
    cert = next((c for c in certificates if c["id"] == cert_id), None)
    if not cert:
        await query.answer("Сертификат не найден", show_alert=True)
        return
    
    date_str = cert["created_at"][:10]
    text = get_text(lang, "certificate_view", date_str)
    
    await context.bot.send_photo(chat_id=chat_id, photo=cert["file_id"], caption=text, parse_mode=ParseMode.MARKDOWN)
    
async def my_certificates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
    # Получаем список сертификатов из БД
    certificates = await get_user_certificates(user_id)
    
    if not certificates:
        text = get_text(lang, "no_certificates")
        # Просто отправляем сообщение, меню редактировать тут не обязательно
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
        return
    
    text = get_text(lang, "total_certificates", len(certificates)) + "\n\n"
    keyboard = []
    
    # Формируем кнопки для каждого сертификата
    for cert in certificates:
        date_str = cert["created_at"][:10]
        btn_text = f"📜 {date_str}"
        # Callback data должен содержать ID сертификата
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"view_cert_{cert['id']}")])
    
    keyboard.append([InlineKeyboardButton("↩️ " + get_button_text(lang, "back"), callback_data="my_stats")])
    
    await context.bot.send_message(
        chat_id=chat_id, 
        text=text, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode=ParseMode.MARKDOWN
    )
                                
async def sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
    # Ссылка на твой стикерпак. Замени 'BintyPack' на название твоего пакета в Telegram
    # Ссылка обычно выглядит так: https://t.me/addstickers/NameOfPack
    sticker_pack_link = "https://t.me/addstickers/bintystickers" 

    text = get_text(lang, "sticker_pack_text")
    
    # Создаем кнопку с ссылкой
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Добавить стикеры", url=sticker_pack_link)],
        [InlineKeyboardButton("↩️ " + get_button_text(lang, "back_to_menu"), callback_data="back_to_menu")]
    ])
    
    await delete_previous_and_send(chat_id, user_id, text, context, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
            
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
    await update_streak(user_id)
    await check_and_award_achievements(user_id, 'streak')
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        await update_user_title(user_id, update.effective_chat.id, context)
    
    # Удаляем контентное сообщение, если есть
    if user_id in last_responses:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_responses[user_id])
            del last_responses[user_id]
        except:
            pass
    
    page = context.user_data.get('leaderboard_page', 0)
    limit = 5
    offset = page * limit
    lb = await get_leaderboard(limit=limit, offset=offset)
    total = await get_leaderboard_count()
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    
    if lb:
        text = get_text(lang, "leaderboard_title")
        for i, (uid, count, total_score) in enumerate(lb, offset + 1):
            title = get_leaderboard_title(i, lang)
            if title:
                text += f"**{title}**\n"
            text += get_text(lang, "leaderboard_row", i, uid, count, total_score)
        text += get_text(lang, "leaderboard_page", page + 1, total_pages)
        
        position = await get_user_position(user_id)
        if position > 0:
            title = get_leaderboard_title(position, lang)
            if title:
                text += f"\n\n📍 **Your position:** {position} — {title}"
            else:
                text += get_text(lang, "leaderboard_your_position", position)
        
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ " + get_button_text(lang, "prev"), callback_data="lb_prev"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(get_button_text(lang, "next") + " ▶️", callback_data="lb_next"))
        nav_buttons.append(InlineKeyboardButton("↩️ " + get_button_text(lang, "back_to_menu"), callback_data="back_to_menu"))
        reply_markup = InlineKeyboardMarkup([nav_buttons]) if nav_buttons else None
        
        final_text = add_hooks(lang, text)
        
        # Редактируем меню
        if user_id in menu_message_ids:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=menu_message_ids[user_id],
                    text=final_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                if "message is not modified" not in str(e):
                    msg = await context.bot.send_message(
                        chat_id=chat_id,
                        text=final_text,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.HTML
                    )
                    menu_message_ids[user_id] = msg.message_id
        else:
            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=final_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            menu_message_ids[user_id] = msg.message_id
    else:
        empty_text = get_text(lang, "leaderboard_empty")
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("↩️ " + get_button_text(lang, "back_to_menu"), callback_data="back_to_menu")]
        ])
        if user_id in menu_message_ids:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=menu_message_ids[user_id],
                    text=empty_text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                if "message is not modified" not in str(e):
                    msg = await context.bot.send_message(
                        chat_id=chat_id,
                        text=empty_text,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    menu_message_ids[user_id] = msg.message_id
        else:
            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=empty_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
            menu_message_ids[user_id] = msg.message_id
                        
async def lb_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['leaderboard_page'] = context.user_data.get('leaderboard_page', 0) + 1
    await leaderboard(update, context)


async def lb_prev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['leaderboard_page'] = max(0, context.user_data.get('leaderboard_page', 0) - 1)
    await leaderboard(update, context)
    
async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает подтверждение подписки"""
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
    if not await check_rate_limit(user_id):
        await query.message.reply_text(TEXTS[lang].get("rate_limit", "⏳ Too many requests."))
        return
        
    await update_streak(user_id)
    await check_and_award_achievements(user_id, 'streak')
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        await update_user_title(user_id, update.effective_chat.id, context)
    
    if await is_subscribed(user_id):
        await delete_previous_and_send(chat_id, user_id, get_text(lang, "already_subscribed"), context)
    else:
        confirm_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes", callback_data="confirm_subscribe"),
             InlineKeyboardButton("❌ No", callback_data="cancel_subscribe")]
        ])
        await delete_previous_and_send(chat_id, user_id, get_text(lang, "subscribe_confirm"), context, reply_markup=confirm_kb)


async def confirm_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await subscribe_user(user_id)
    await query.answer(get_text(lang, "subscribe"), show_alert=True)
    await query.message.delete()
    await update_menu(chat_id, user_id, context, lang)

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает подтверждение отписки"""
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
    if not await check_rate_limit(user_id):
        await query.message.reply_text(TEXTS[lang].get("rate_limit", "⏳ Too many requests."))
        return
        
    await update_streak(user_id)
    await check_and_award_achievements(user_id, 'streak')
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        await update_user_title(user_id, update.effective_chat.id, context)
    
    if not await is_subscribed(user_id):
        await delete_previous_and_send(chat_id, user_id, get_text(lang, "not_subscribed"), context)
    else:
        confirm_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes", callback_data="confirm_unsubscribe"),
             InlineKeyboardButton("❌ No", callback_data="cancel_unsubscribe")]
        ])
        await delete_previous_and_send(chat_id, user_id, get_text(lang, "unsubscribe_confirm"), context, reply_markup=confirm_kb)

async def confirm_unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await unsubscribe_user(user_id)
    await query.answer(get_text(lang, "unsubscribe"), show_alert=True)
    await query.message.delete()
    await update_menu(chat_id, user_id, context, lang)
    
async def cancel_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    await delete_previous_and_send(chat_id, user_id, get_text(lang, "action_cancelled"), context)
    
async def update_user_title(user_id: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Обновляет титул пользователя в чате на основе его достижений"""
    try:
        lang = await get_language(user_id)
        titles = TEXTS[lang].get("titles")
        if not titles:
            return
        
        stats = await get_user_stats(user_id)
        streak_info = await get_streak_info(user_id)
        position = await get_user_position(user_id)
        
        title = None
        
        if position == 1:
            title = titles.get("top1")
        elif position == 2:
            title = titles.get("top2")
        elif position == 3:
            title = titles.get("top3")
        elif streak_info and streak_info.get("current_streak", 0) >= 30:
            title = titles.get("streak30")
        elif streak_info and streak_info.get("current_streak", 0) >= 7:
            title = titles.get("streak7")
        elif stats and stats.get("count", 0) >= 100:
            title = titles.get("fumble100")
        elif stats and stats.get("count", 0) >= 50:
            title = titles.get("fumble50")
        elif stats and stats.get("count", 0) >= 10:
            title = titles.get("fumble10")
        
        if title:
            await context.bot.promote_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                can_manage_chat=False
            )
            await context.bot.set_chat_administrator_custom_title(
                chat_id=chat_id,
                user_id=user_id,
                custom_title=title
            )
    except Exception as e:
        logging.error(f"Failed to update title for user {user_id}: {e}")

async def language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await update_streak(user_id)
    await check_and_award_achievements(user_id, 'streak')
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        await update_user_title(user_id, update.effective_chat.id, context)
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es")],
        [InlineKeyboardButton("🇨🇳 中文", callback_data="lang_zh")],
        [InlineKeyboardButton("↩️ Назад", callback_data="back_to_menu")]
    ])
    
    await query.edit_message_text(
        "🌐 Выбери язык / Select language:",
        reply_markup=kb
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
    await update_streak(user_id)
    await check_and_award_achievements(user_id, 'streak')
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        await update_user_title(user_id, update.effective_chat.id, context)
    
    help_text = get_text(lang, "help")
    final_text = add_hooks(lang, help_text)
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ " + get_text(lang, "close"), callback_data="close_message")]
    ])
    
    await delete_previous_and_send(chat_id, user_id, final_text, context, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    
async def close_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    await query.answer()
    
    if user_id in last_responses:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_responses[user_id])
            del last_responses[user_id]
        except:
            pass
    await query.message.delete()
                
async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    await update_menu(chat_id, user_id, context, lang)
        
async def quests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
    await update_streak(user_id)
    await check_and_award_achievements(user_id, 'streak')
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        await update_user_title(user_id, update.effective_chat.id, context)
    
    if user_id in last_responses:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_responses[user_id])
            del last_responses[user_id]
        except:
            pass
    
    await generate_daily_quests_for_user(user_id)
    active_quests = await get_user_active_quests(user_id)
    completed_quests = await get_user_completed_quests(user_id, limit=3)
    
    text = f"🎯 **{TEXTS[lang].get('quests_title', 'QUESTS')}**\n\n"
    
    if active_quests:
        text += "*" + get_text(lang, "active_quests") + ":*\n"
        for uq in active_quests:
            quest = uq.get("quests", {})
            name = quest.get(f"name_{lang}", quest.get("name_en", "Quest"))
            progress = uq["progress"]
            target = quest["condition_value"]
            filled = "🟩" * progress
            empty = "⬛" * (target - progress)
            bar = filled + empty
            reward = quest.get("reward_points", 0)
            status = " ✅" if uq["completed"] else ""
            text += f"\n▫️ {name}{status}\n{bar} {progress}/{target}\n└ 💰 +{reward}\n"
    else:
        text += "*" + get_text(lang, "no_active_quests") + "*\n"
    
    if completed_quests:
        text += "\n*" + get_text(lang, "recently_completed") + ":*\n"
        for uq in completed_quests:
            quest = uq.get("quests", {})
            name = quest.get(f"name_{lang}", quest.get("name_en", "Quest"))
            claimed = "✅" if uq["reward_claimed"] else "⏳"
            text += f"{claimed} {name}\n"
    
    keyboard = []
    for uq in active_quests:
        if uq["completed"] and not uq["reward_claimed"]:
            quest = uq.get("quests", {})
            name = quest.get(f"name_{lang}", quest.get("name_en", "Quest"))[:15]
            keyboard.append([InlineKeyboardButton(f"🎁 {name}", callback_data=f"claim_quest_{uq['id']}")])
    
    keyboard.append([InlineKeyboardButton("↩️ " + get_button_text(lang, "back"), callback_data="game_center")])
    keyboard.append([InlineKeyboardButton("🏠 " + get_button_text(lang, "back_to_menu"), callback_data="back_to_menu")])
    
    if user_id in menu_message_ids:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=menu_message_ids[user_id],
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
    else:
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        menu_message_ids[user_id] = msg.message_id

async def claim_quest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает клейм награды квеста"""
    query = update.callback_query
    user_id = query.from_user.id
    lang = await get_language(user_id)
    data = query.data
    
    quest_id = int(data.replace("claim_quest_", ""))
    
    result = await claim_quest_reward(user_id, quest_id)
    
    if result["success"]:
        text = f"✅ **Reward claimed!**\n\n+{result['reward_points']} fumble points"
        if result['reward_binty'] > 0:
            text += f"\n+{result['reward_binty']} $BINTY"
        await query.answer(text, show_alert=True)
    else:
        await query.answer(f"❌ {result['error']}", show_alert=True)
    
    # Обновляем меню квестов
    await quests(update, context)


async def referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
    await update_streak(user_id)
    
    if user_id in last_responses:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_responses[user_id])
            del last_responses[user_id]
        except:
            pass
    
    count = await get_referrals_count(user_id)
    link = f"https://t.me/BintyAgentBot?start=ref_{user_id}"
    
    title = TEXTS[lang].get('referrals_title', 'РЕФЕРАЛЫ')
    invited = get_text(lang, 'invited')
    your_link = get_text(lang, 'your_link')
    info = get_text(lang, "referral_info")
    
    text = f"👥 <b>{title}</b>\n\n"
    text += f"▫️ {invited}: <b>{count}</b>\n"
    text += f"▫️ {your_link}:\n<code>{link}</code>\n\n"
    text += info
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("↩️ " + get_button_text(lang, "back"), callback_data="game_center")],
        [InlineKeyboardButton("🏠 " + get_button_text(lang, "back_to_menu"), callback_data="back_to_menu")]
    ])
    
    if user_id in menu_message_ids:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=menu_message_ids[user_id],
                text=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logging.error(f"REFERRALS: edit failed: {e}")
    else:
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        menu_message_ids[user_id] = msg.message_id
        
async def signal_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
    await update_streak(user_id)
    await check_and_award_achievements(user_id, 'streak')
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        await update_user_title(user_id, update.effective_chat.id, context)
    
    # Удаляем контентное сообщение, если есть
    if user_id in last_responses:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_responses[user_id])
            del last_responses[user_id]
        except:
            pass
    
    history = await get_signal_history(user_id, limit=10)
    if not history:
        text = get_text(lang, "no_history")
    else:
        lines = [f"{h.get('created_at', '')[:10]}: {h.get('signal_text', '')[:50]}..." for h in history]
        text = get_text(lang, "signal_history_text", "\n".join(lines))
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("↩️ " + get_button_text(lang, "back"), callback_data="my_stats")]
    ])
    
    # Редактируем меню
    if user_id in menu_message_ids:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=menu_message_ids[user_id],
                text=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logging.error(f"Signal history edit failed: {e}")
    else:
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        menu_message_ids[user_id] = msg.message_id

async def fumble_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
    await update_streak(user_id)
    await check_and_award_achievements(user_id, 'streak')
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        await update_user_title(user_id, update.effective_chat.id, context)
    
    # Удаляем контентное сообщение, если есть
    if user_id in last_responses:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_responses[user_id])
            del last_responses[user_id]
        except:
            pass
    
    history = await get_fumble_history(user_id, limit=10)
    if not history:
        text = get_text(lang, "no_history")
    else:
        lines = [f"{h.get('created_at', '')[:10]}: Score {h.get('score', 0)}/10 ({h.get('type', 'manual')})" for h in history]
        text = get_text(lang, "fumble_history_text", "\n".join(lines))
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("↩️ " + get_button_text(lang, "back"), callback_data="my_stats")]
    ])
    
    # Редактируем меню
    if user_id in menu_message_ids:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=menu_message_ids[user_id],
                text=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logging.error(f"Fumble history edit failed: {e}")
    else:
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        menu_message_ids[user_id] = msg.message_id
    
async def game_center(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
    await update_streak(user_id)
    await check_and_award_achievements(user_id, 'streak')
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        await update_user_title(user_id, update.effective_chat.id, context)
    
    # Удаляем контентное сообщение
    if user_id in last_responses:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_responses[user_id])
            del last_responses[user_id]
        except:
            pass
    
    # Редактируем меню
    if user_id in menu_message_ids:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=menu_message_ids[user_id],
                text=TEXTS[lang].get("game_center_title", "🎮 GAME CENTER"),
                reply_markup=get_game_center_menu(lang),
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
    
async def achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
    await update_streak(user_id)
    await check_and_award_achievements(user_id, 'streak')
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        await update_user_title(user_id, update.effective_chat.id, context)
    
    # Удаляем контентное сообщение, если есть
    if user_id in last_responses:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_responses[user_id])
            del last_responses[user_id]
        except:
            pass
    
    earned = await get_user_achievements(user_id)
    earned_keys = set([a["achievement_key"] for a in earned]) if earned else set()
    all_achievements = await get_all_achievements(lang)
    
    total_earned = len(earned_keys)
    total_all = len(all_achievements)
    
    text = f"🏆 **{TEXTS[lang].get('achievements_title', 'ACHIEVEMENTS')}**\n"
    text += f"▫️ {get_text(lang, 'progress')}: {total_earned}/{total_all}\n\n"
    
    categories = {
        "fumble": {"icon": "🤡", "name": {"en": "Fumbles", "ru": "Фамблы", "es": "Fumbles", "zh": "失误"}},
        "signal": {"icon": "📡", "name": {"en": "Signals", "ru": "Сигналы", "es": "Señales", "zh": "信号"}},
        "streak": {"icon": "🔥", "name": {"en": "Streaks", "ru": "Серии", "es": "Rachas", "zh": "连续"}},
        "wallet": {"icon": "💼", "name": {"en": "Wallet", "ru": "Кошелёк", "es": "Cartera", "zh": "钱包"}},
        "social": {"icon": "👥", "name": {"en": "Social", "ru": "Соцсети", "es": "Social", "zh": "社交"}},
        "special": {"icon": "🌟", "name": {"en": "Special", "ru": "Особые", "es": "Especial", "zh": "特殊"}}
    }
    
    cat_achievements = {cat: [] for cat in categories}
    for ach in all_achievements:
        cat = get_category(ach["achievement_key"])
        if cat in cat_achievements:
            cat_achievements[cat].append(ach)
    
    for cat, ach_list in cat_achievements.items():
        if not ach_list:
            continue
        cat_name = categories[cat]["name"].get(lang, cat)
        cat_icon = categories[cat]["icon"]
        earned_in_cat = sum(1 for a in ach_list if a["achievement_key"] in earned_keys)
        total_in_cat = len(ach_list)
        text += f"{cat_icon} **{cat_name}** ({earned_in_cat}/{total_in_cat})\n"
        for ach in ach_list[:8]:
            key = ach["achievement_key"]
            is_earned = key in earned_keys
            icon = ach.get("icon", "🏅")
            name = ach.get(f"name_{lang}", ach.get("name_en", key))
            text += f"  {'✅' if is_earned else '🔒'} {icon} {name}\n"
        text += "\n"
    
    keyboard = [
        [InlineKeyboardButton("↩️ " + get_button_text(lang, "back"), callback_data="game_center")],
        [InlineKeyboardButton("🏠 " + get_button_text(lang, "back_to_menu"), callback_data="back_to_menu")]
    ]
    
    # Редактируем меню
    if user_id in menu_message_ids:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=menu_message_ids[user_id],
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
    else:
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        menu_message_ids[user_id] = msg.message_id      

def get_category(key: str) -> str:
    """Определяет категорию ачивки по ключу"""
    if key in ["first_fumble", "silver_loser", "gold_loser", "platinum_loser", "king_of_bottom"]:
        return "fumble"
    elif key in ["signal_master", "signal_legend"]:
        return "signal"
    elif key in ["masochist", "godless"]:
        return "streak"
    elif key in ["hell_holder", "crypto_archaeologist", "paranoid", "liquidity_sponsor"]:
        return "wallet"
    elif key in ["referral_baron"]:
        return "social"
    else:
        return "special"

async def my_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
    await update_streak(user_id)
    await check_and_award_achievements(user_id, 'streak')
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        await update_user_title(user_id, update.effective_chat.id, context)
    
    logging.info(f"MY_STATS: called by user {user_id}")
    
    try:
        # Удаляем контентное сообщение
        if user_id in last_responses:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=last_responses[user_id])
                del last_responses[user_id]
            except Exception as e:
                logging.warning(f"MY_STATS: failed to delete content: {e}")

        # Получаем данные
        stats = await get_user_stats(user_id)
        logging.info(f"MY_STATS: stats = {stats}")
        
        streak_info = await get_streak_info(user_id)
        logging.info(f"MY_STATS: streak_info = {streak_info}")
        
        position = await get_user_position(user_id)
        logging.info(f"MY_STATS: position = {position}")
        
        # Безопасно извлекаем значения (защита от None)
        avg_score = stats.get("average", 0) if stats else 0
        total_fumbles = stats.get("count", 0) if stats else 0
        signal_clicks = stats.get("signal_clicks", 0) if stats else 0
        
        level = get_level(avg_score)
        level_name = get_level_name(level, lang)
        
        current_streak = streak_info.get("current_streak", 0) if streak_info else 0
        
        referrals = await get_referrals_count(user_id)
        
        # Формируем текст
        text = get_text(
            lang, "my_stats",
            level,
            level_name,
            total_fumbles,
            avg_score,
            signal_clicks,
            current_streak,
            referrals,
            position
        )
        
        keyboard = get_my_stats_menu(lang)
        
        # Редактируем меню
        if user_id in menu_message_ids:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=menu_message_ids[user_id],
                    text=text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN
                )
                logging.info(f"MY_STATS: menu edited for user {user_id}")
            except Exception as e:
                logging.error(f"MY_STATS: edit failed: {e}")
                msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN
                )
                menu_message_ids[user_id] = msg.message_id
        else:
            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
            menu_message_ids[user_id] = msg.message_id
            logging.info(f"MY_STATS: new menu sent for user {user_id}")
            
    except Exception as e:
        logging.error(f"MY_STATS crashed for user {user_id}: {e}", exc_info=True)
        await query.message.reply_text("❌ Ошибка при загрузке статистики. Попробуй позже.")
                                
async def suffering_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = await get_language(user_id)
    await query.answer()
    
    await update_streak(user_id)
    await check_and_award_achievements(user_id, 'streak')
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        await update_user_title(user_id, update.effective_chat.id, context)
    
    if user_id in last_responses:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_responses[user_id])
            del last_responses[user_id]
        except:
            pass
    
    info = await get_streak_info(user_id)
    active_days = set(info.get("active_days", []))
    today = date.today()
    first_day = today.replace(day=1)
    start_date = first_day - timedelta(days=first_day.weekday())
    
    weekdays = {
        "en": ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"],
        "ru": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
        "es": ["Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do"],
        "zh": ["一", "二", "三", "四", "五", "六", "日"]
    }
    days_header = weekdays.get(lang, weekdays["en"])
    month_names = {
        "en": today.strftime("%B %Y"),
        "ru": ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", 
               "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"][today.month-1] + f" {today.year}",
        "es": today.strftime("%B %Y"),
        "zh": f"{today.year}年{today.month}月"
    }
    month_title = month_names.get(lang, month_names["en"])
    
    text = f"📅 **{month_title}**\n\n`"
    for day in days_header:
        text += f"{day} "
    text += "`\n"
    
    current = start_date
    for week in range(4):
        text += "`"
        for day in range(7):
            current_str = current.isoformat()
            if current.month != today.month:
                text += "⚫ "
            elif current_str in active_days:
                text += "🔥 " if current == today else "🟢 "
            else:
                text += "⭕ " if current == today else "⚫ "
            current += timedelta(days=1)
        text += "`\n"
    
    text += "\n🟢 " + get_text(lang, "active_day") + "  ⚫ " + get_text(lang, "inactive_day")
    text += "\n🔥 " + get_text(lang, "today_active") + "  ⭕ " + get_text(lang, "today_inactive")
    text += f"\n\n▫️ {get_text(lang, 'current_streak')}: **{info['current_streak']}**"
    text += f"\n▫️ {get_text(lang, 'longest_streak')}: **{info['max_streak']}**"
    
    keyboard = [
        [InlineKeyboardButton("↩️ " + get_button_text(lang, "back"), callback_data="game_center")],
        [InlineKeyboardButton("🏠 " + get_button_text(lang, "back_to_menu"), callback_data="back_to_menu")]
    ]
    
    if user_id in menu_message_ids:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=menu_message_ids[user_id],
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
    else:
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        menu_message_ids[user_id] = msg.message_id
    
async def delete_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    lang = await get_language(user_id)
    await delete_wallet_address(user_id)
    await query.answer()
    await query.message.reply_text(get_text(lang, "wallet_deleted"))

# ... остальные обработчики (можно добавить по аналогии)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    # Маршрутизация
    if data == "signal": await signal(update, context)
    elif data == "fumble": await fumble_start(update, context)
    elif data == "portfolio": await portfolio(update, context)
    elif data == "price": await price(update, context)
    elif data == "holders": await holders(update, context)
    elif data == "balance": await balance(update, context)
    elif data == "meme": await meme(update, context)
    elif data == "sticker": await sticker(update, context)
    elif data == "leaderboard": await leaderboard(update, context)
    elif data == "language": await language(update, context)
    elif data == "subscribe": await subscribe(update, context)
    elif data == "unsubscribe": await unsubscribe(update, context)
    elif data == "help": await help_command(update, context)
    elif data == "game_center": await game_center(update, context)
    elif data == "my_stats": await my_stats(update, context)
    elif data == "achievements": await achievements(update, context)
    elif data == "certificate": await certificate(update, context)
    elif data == "suffering_calendar": await suffering_calendar(update, context)
    elif data == "quests": await quests(update, context)
    elif data == "referrals": await referrals(update, context)
    elif data == "signal_history": await signal_history(update, context)
    elif data == "fumble_history": await fumble_history(update, context)
    elif data.startswith("fumble_answer_"): await fumble_answer_handler(update, context)
    elif data == "fumble_cancel": await fumble_cancel_handler(update, context)
    elif data == "manual_fumble": await manual_fumble_start(update, context)
    elif data == "back_to_menu": await back_to_menu(update, context)
    elif data == "cancel_balance": await cancel_balance(update, context)
    elif data == "confirm_subscribe": await confirm_subscribe(update, context)
    elif data == "confirm_unsubscribe": await confirm_unsubscribe(update, context)
    elif data == "cancel_subscribe": await cancel_action(update, context)
    elif data == "cancel_unsubscribe": await cancel_action(update, context)
    elif data == "lb_next": await lb_next(update, context)
    elif data == "lb_prev": await lb_prev(update, context)
    elif data == "delete_wallet":
        await delete_wallet(update, context)
    elif data.startswith("claim_quest_"):
        await claim_quest(update, context)
    elif data == "close_message":
        user_id = query.from_user.id
        chat_id = query.message.chat_id
        if user_id in last_responses:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=last_responses[user_id])
                del last_responses[user_id]
            except:
                pass
        await query.message.delete()
    elif data.startswith("lang_"):
        lang_code = data.split("_")[1]
        user_id = query.from_user.id
        chat_id = query.message.chat_id
        await set_language(user_id, lang_code)
        await query.answer(f"✅ Язык изменён")
        await update_menu(chat_id, user_id, context, lang_code)
    elif data == "my_certificates": 
        await my_certificates(update, context)
    elif data.startswith("view_cert_"): 
        await view_certificate(update, context)
            
# ... конец button_callback ...

# ==================== HTTP-СЕРВЕР ДЛЯ RENDER ====================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")
    def log_message(self, format, *args):
        pass

def run_health_server():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()


# ==================== MAIN ====================
def main():
    init_supabase()
    start_scheduler()
    
    global cached_fumble_questions
    cached_fumble_questions = asyncio.run(fetch_fumble_questions())
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_balance_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(PollAnswerHandler(handle_poll_answer))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # ========== ДОБАВИТЬ ПЛАНИРОВЩИК ==========
    job_queue = app.job_queue
    if job_queue:
        # Авто-сигналы каждые 6 часов
        job_queue.run_repeating(lambda ctx: asyncio.create_task(send_auto_signals()), interval=21600, first=10)
        # Сигнал дня раз в 24 часа
        job_queue.run_repeating(lambda ctx: asyncio.create_task(send_signal_of_the_day()), interval=86400, first=60)
        # Еженедельный лидерборд: каждое воскресенье в 23:59 UTC
        # Еженедельный лидерборд: воскресенье 23:59 UTC
        job_queue.run_daily(
            lambda ctx: asyncio.create_task(send_weekly_leaderboard()),
            time=time(hour=23, minute=59),
            days=(6,)
        )
    # =========================================
    
    logging.info("🚀 BINTY Agent starting with polling...")
    print("🚀 Bot is starting...")
    app.run_polling()
    print("❌ Bot stopped!")