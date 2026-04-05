import os
import random
import logging
import asyncio
import aiohttp
import re
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# Import our custom modules
import database as db
from texts import TEXTS, get_text

# Configure logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TOKEN_ADDRESS = os.getenv("TOKEN_ADDRESS", "FumblCoinAddressHere")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# ==================== UTILITIES ====================

def is_valid_solana_address(address):
    return bool(re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", address))

def get_button_text(lang, key):
    return TEXTS[lang]["buttons"].get(key, key)

def get_main_menu(lang):
    buttons = [
        [InlineKeyboardButton(get_button_text(lang, "signal"), callback_data="signal"),
         InlineKeyboardButton(get_button_text(lang, "fumble"), callback_data="fumble")],
        [InlineKeyboardButton(get_button_text(lang, "portfolio"), callback_data="portfolio"),
         InlineKeyboardButton(get_button_text(lang, "price"), callback_data="price")],
        [InlineKeyboardButton(get_button_text(lang, "leaderboard"), callback_data="leaderboard"),
         InlineKeyboardButton(get_button_text(lang, "referral_btn"), callback_data="referral")],
        [InlineKeyboardButton(get_button_text(lang, "subscribe"), callback_data="subscribe"),
         InlineKeyboardButton(get_button_text(lang, "language"), callback_data="language_menu")],
        [InlineKeyboardButton(get_button_text(lang, "roast_me_btn"), callback_data="roast_me"),
         InlineKeyboardButton(get_button_text(lang, "tomorrow_btn"), callback_data="tomorrow")],
        [InlineKeyboardButton(get_button_text(lang, "buy"), url=f"https://pump.fun/coin/{TOKEN_ADDRESS}"),
         InlineKeyboardButton(get_button_text(lang, "chat"), url="https://t.me/fumblcoin")]
    ]
    return InlineKeyboardMarkup(buttons)

# ==================== IMAGE GENERATION ====================

def generate_share_card(user_name, rank, level, fumbles):
    width, height = 600, 400
    img = Image.new('RGB', (width, height), color='#121212')
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, width-10, height-10], outline='#ff5252', width=5)
    
    draw.text((50, 50), "🤡 FUMBL DEGEN CARD", fill='#ff5252')
    draw.text((50, 120), f"NAME: {user_name}", fill='white')
    draw.text((50, 170), f"RANK: {rank}", fill='#ff5252')
    draw.text((50, 220), f"LEVEL: {level}", fill='white')
    draw.text((50, 270), f"TOTAL FUMBLES: {fumbles}", fill='white')
    draw.text((50, 340), "PROUDLY LOSING MONEY SINCE 2024", fill='#555')
    
    bio = BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

# ==================== MESSAGE MANAGEMENT ====================

async def update_interface(update: Update, context: ContextTypes.DEFAULT_TYPE, text, reply_markup=None, photo=None):
    query = update.callback_query
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if "main_msg_id" not in context.user_data:
        context.user_data["main_msg_id"] = None
    
    try:
        if photo:
            if context.user_data["main_msg_id"]:
                try:
                    await context.bot.edit_message_media(
                        chat_id=chat_id,
                        message_id=context.user_data["main_msg_id"],
                        media=InputMediaPhoto(media=photo, caption=text, parse_mode=ParseMode.MARKDOWN),
                        reply_markup=reply_markup
                    )
                    return
                except Exception:
                    pass
            
            msg = await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
            context.user_data["main_msg_id"] = msg.message_id
        else:
            if query and context.user_data["main_msg_id"] == query.message.message_id:
                await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
            elif context.user_data["main_msg_id"]:
                try:
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=context.user_data["main_msg_id"], text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
                except Exception:
                    msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
                    context.user_data["main_msg_id"] = msg.message_id
            else:
                msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
                context.user_data["main_msg_id"] = msg.message_id
    except Exception as e:
        logger.error(f"Error updating interface: {e}")
        msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        context.user_data["main_msg_id"] = msg.message_id

# ==================== HANDLERS ====================

async def check_achievements(user_id, lang, context: ContextTypes.DEFAULT_TYPE):
    stats = db.get_user_stats(user_id)
    new_achievements = []
    if stats["fumble_count"] == 1 and db.grant_achievement(user_id, "first_fumble"):
        new_achievements.append(get_text(lang, "achievements", index="first_fumble"))
    if stats["streak"] >= 3 and db.grant_achievement(user_id, "streak_3"):
        new_achievements.append(get_text(lang, "achievements", index="streak_3"))
    if stats["interaction_count"] >= 100 and db.grant_achievement(user_id, "clicker_100"):
        new_achievements.append(get_text(lang, "achievements", index="clicker_100"))
    if new_achievements:
        msg = "🏆 *NEW ACHIEVEMENT UNLOCKED!*\n\n" + "\n".join(new_achievements)
        await context.bot.send_message(chat_id=user_id, text=msg, parse_mode=ParseMode.MARKDOWN)

async def trigger_random_event(user_id, lang, context: ContextTypes.DEFAULT_TYPE):
    if random.random() < 0.05:
        event_key = random.choice(["rug_pull", "whale_dump", "pump_fake"])
        event_text = get_text(lang, "events").get(event_key, "Something bad happened.")
        await context.bot.send_message(chat_id=user_id, text=f"⚠️ *RANDOM EVENT:* {event_text}", parse_mode=ParseMode.MARKDOWN)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = db.get_language(user_id)
    db.update_interaction(user_id, "start")
    stats = db.get_user_stats(user_id)
    if context.args and context.args[0].isdigit():
        db.add_referral(int(context.args[0]), user_id)
    is_new = stats["interaction_count"] <= 1
    welcome_text = get_text(lang, "welcome_new") if is_new else get_text(lang, "welcome_old")
    rank = get_text(lang, "ranks", index=stats["level"]-1)
    status_line = f"🎖 Rank: *{rank}* | 🆙 Lvl: *{stats['level']}* | 🔥 Streak: *{stats['streak']}*"
    full_text = f"🤡 *AGENT FUMBL:* {welcome_text}\n\n{status_line}\n\n_{get_text(lang, 'mood_responses', mood=stats['mood_level'])}_"
    await update_interface(update, context, full_text, get_main_menu(lang))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang = db.get_language(user_id)
    data = query.data
    db.update_interaction(user_id, data)
    await check_achievements(user_id, lang, context)
    await trigger_random_event(user_id, lang, context)
    stats = db.get_user_stats(user_id)
    mood = stats["mood_level"]
    rank = get_text(lang, "ranks", index=stats["level"]-1)
    agent_prefix = f"🤡 *AGENT FUMBL (Lvl {stats['level']} {rank}):*\n\n"
    
    if data == "main_menu":
        await update_interface(update, context, agent_prefix + get_text(lang, "mood_responses", mood=mood), get_main_menu(lang))
    elif data == "signal":
        await update_interface(update, context, agent_prefix + "⌛ " + get_text(lang, "signal_pause"))
        await asyncio.sleep(1.2)
        signal = get_text(lang, "signal")
        await update_interface(update, context, agent_prefix + f"📈 *SIGNAL:*\n\n{signal}", get_main_menu(lang))
    elif data == "fumble":
        options = TEXTS[lang]["fumble_options"]
        buttons = [[InlineKeyboardButton(opt, callback_data=f"f_opt_{i}")] for i, opt in enumerate(options)]
        buttons.append([InlineKeyboardButton("◀️ Back", callback_data="main_menu")])
        await update_interface(update, context, agent_prefix + get_text(lang, "fumble_question"), InlineKeyboardMarkup(buttons))
    elif data.startswith("f_opt_"):
        db.save_fumble(user_id, 10)
        await update_interface(update, context, agent_prefix + "⌛ " + get_text(lang, "fumble_pause"))
        await asyncio.sleep(1.2)
        await update_interface(update, context, agent_prefix + f"🤡 *RECORDED.*\nYour XP increased. Your dignity decreased.", get_main_menu(lang))
    elif data == "portfolio":
        pos = db.get_user_position(user_id)
        text = agent_prefix + f"💰 *PORTFOLIO PAIN*\n\nRank: #{pos}\nFumbles: {stats['fumble_count']}\nStreak: {stats['streak']} days\n\n_{get_text(lang, 'mood_responses', mood=mood)}_"
        buttons = get_main_menu(lang).inline_keyboard
        buttons.append([InlineKeyboardButton(get_button_text(lang, "share_btn"), callback_data="share_card")])
        img = Image.new('RGB', (400, 200), color='black')
        draw = ImageDraw.Draw(img)
        draw.line([(0, 50), (400, 190)], fill='red', width=3)
        bio = BytesIO()
        img.save(bio, 'PNG')
        bio.seek(0)
        await update_interface(update, context, text, InlineKeyboardMarkup(buttons), photo=bio)
    elif data == "share_card":
        user_name = update.effective_user.first_name
        rank = get_text(lang, "ranks", index=stats["level"]-1)
        card = generate_share_card(user_name, rank, stats["level"], stats["fumble_count"])
        await update_interface(update, context, agent_prefix + "Here is your digital proof of failure. Post it and cry.", get_main_menu(lang), photo=card)
    elif data == "roast_me":
        roast = get_text(lang, "roast_me")
        await update_interface(update, context, agent_prefix + f"🔥 *ROAST:*\n\n{roast}", get_main_menu(lang))
    elif data == "tomorrow":
        pred = get_text(lang, "tomorrow_prediction")
        await update_interface(update, context, agent_prefix + f"🔮 *TOMORROW:*\n\n{pred}", get_main_menu(lang))
    elif data == "language_menu":
        buttons = [[InlineKeyboardButton("🇺🇸 English", callback_data="set_lang_en"), InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang_ru")], [InlineKeyboardButton("◀️ Back", callback_data="main_menu")]]
        await update_interface(update, context, agent_prefix + "🌐 Language Selection:", InlineKeyboardMarkup(buttons))
    elif data.startswith("set_lang_"):
        new_lang = data.split("_")[-1]
        db.set_language(user_id, new_lang)
        await update_interface(update, context, f"Language: {new_lang.upper()}", get_main_menu(new_lang))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    lang = db.get_language(user_id)
    db.update_interaction(user_id, "chat_msg")
    stats = db.get_user_stats(user_id)
    if is_valid_solana_address(text):
        db.save_wallet_address(user_id, text)
        db.grant_achievement(user_id, "wallet_linked")
        await update.message.reply_text(f"🤡 *AGENT FUMBL:* Wallet linked. I'll watch your dust.")
        return
    resp = get_text(lang, "ignore_text")
    await update.message.reply_text(f"🤡 *AGENT FUMBL:* {resp}\n\n_{get_text(lang, 'mood_responses', mood=stats['mood_level'])}_")

def main():
    db.init_db()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("FUMBL Degen Simulator v4.2 started.")
    application.run_polling()

if __name__ == "__main__":
    main()
