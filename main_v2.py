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
                    await context.bot.delete_message(chat_id=chat_id, message_id=context.user_data["main_msg_id"])
            
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = db.get_language(user_id)
    stats = db.get_user_stats(user_id)
    
    # Track interaction
    db.update_interaction(user_id, "start")
    
    # Handle referral
    if context.args and context.args[0].isdigit():
        referrer_id = int(context.args[0])
        db.add_referral(referrer_id, user_id)
    
    is_new = stats["interaction_count"] <= 1
    welcome_text = get_text(lang, "welcome_new") if is_new else get_text(lang, "welcome_old")
    
    # Agent character addition
    if not is_new:
        welcome_text = f"🤡 *AGENT FUMBL:* {welcome_text}\n\n"
        welcome_text += f"_{get_text(lang, 'mood_responses', mood=stats['mood_level'])}_"
        
    await update_interface(update, context, welcome_text, get_main_menu(lang))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    lang = db.get_language(user_id)
    data = query.data
    
    # Update memory
    db.update_interaction(user_id, data)
    stats = db.get_user_stats(user_id)
    mood = stats["mood_level"]
    
    # Agent mood prefix
    agent_prefix = f"🤡 *AGENT FUMBL (Mood: {mood}):*\n\n"
    
    if data == "main_menu":
        await update_interface(update, context, agent_prefix + get_text(lang, "mood_responses", mood=mood), get_main_menu(lang))
    
    elif data == "signal":
        await update_interface(update, context, agent_prefix + "⌛ " + get_text(lang, "signal_pause"))
        await asyncio.sleep(1.5)
        signal = get_text(lang, "signal")
        await update_interface(update, context, agent_prefix + f"📈 *SIGNAL:*\n\n{signal}\n\n_{get_text(lang, 'mood_responses', mood=mood)}_", get_main_menu(lang))
        
    elif data == "fumble":
        options = TEXTS[lang]["fumble_options"]
        buttons = []
        for i, opt in enumerate(options):
            buttons.append([InlineKeyboardButton(opt, callback_data=f"f_opt_{i}")])
        buttons.append([InlineKeyboardButton("◀️ Back", callback_data="main_menu")])
        await update_interface(update, context, agent_prefix + get_text(lang, "fumble_question"), InlineKeyboardMarkup(buttons))
        
    elif data.startswith("f_opt_"):
        idx = int(data.split("_")[-1])
        fumble_text = TEXTS[lang]["fumble_options"][idx]
        db.save_fumble(user_id, 10)
        await update_interface(update, context, agent_prefix + "⌛ " + get_text(lang, "fumble_pause"))
        await asyncio.sleep(1.5)
        await update_interface(update, context, agent_prefix + f"🤡 *RECORDED:*\n_{fumble_text}_\n\nYour shame is now permanent in my memory. 📉", get_main_menu(lang))

    elif data == "portfolio":
        pos = db.get_user_position(user_id)
        wallet = db.get_wallet_address(user_id) or "Not linked"
        text = agent_prefix + f"💰 *PORTFOLIO PAIN*\n\nWallet: `{wallet}`\nFumbles: {stats['fumble_count']}\nRank: #{pos}\nInteractions: {stats['interaction_count']}\n\n"
        text += f"_{get_text(lang, 'mood_responses', mood=mood)}_"
        
        # Fake chart
        width, height = 400, 200
        img = Image.new('RGB', (width, height), color='black')
        draw = ImageDraw.Draw(img)
        draw.line([(0, 50), (100, 80), (200, 150), (400, 190)], fill='red', width=3)
        draw.text((10, 10), "REKT", fill='white')
        bio = BytesIO()
        img.save(bio, 'PNG')
        bio.seek(0)
        await update_interface(update, context, text, get_main_menu(lang), photo=bio)

    elif data == "referral":
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        text = agent_prefix + f"🤝 *PARTNER PROGRAM*\n\nYour Link: `{ref_link}`\nInvited: {stats['referrals']}\n\n"
        text += f"_{get_text(lang, 'referral_pain')}_"
        await update_interface(update, context, text, get_main_menu(lang))

    elif data == "roast_me":
        roast = get_text(lang, "roast_me")
        await update_interface(update, context, agent_prefix + f"🔥 *ROAST:*\n\n{roast}\n\n_{get_text(lang, 'mood_responses', mood=mood)}_", get_main_menu(lang))

    elif data == "tomorrow":
        pred = get_text(lang, "tomorrow_prediction")
        await update_interface(update, context, agent_prefix + f"🔮 *TOMORROW:*\n\n{pred}", get_main_menu(lang))

    elif data == "language_menu":
        buttons = [
            [InlineKeyboardButton("🇺🇸 English", callback_data="set_lang_en"), InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang_ru")],
            [InlineKeyboardButton("◀️ Back", callback_data="main_menu")]
        ]
        await update_interface(update, context, agent_prefix + "🌐 Select Language:", InlineKeyboardMarkup(buttons))

    elif data.startswith("set_lang_"):
        new_lang = data.split("_")[-1]
        db.set_language(user_id, new_lang)
        await update_interface(update, context, f"Language set to {new_lang.upper()}", get_main_menu(new_lang))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    lang = db.get_language(user_id)
    db.update_interaction(user_id, "chat_msg")
    stats = db.get_user_stats(user_id)
    
    if is_valid_solana_address(text):
        db.save_wallet_address(user_id, text)
        await update.message.reply_text(f"🤡 *AGENT FUMBL:* Wallet linked. I'll watch you lose from here.")
        return

    # Character reaction to text
    responses = TEXTS[lang].get("ignore_text", "Press buttons, loser.")
    if isinstance(responses, list):
        resp = random.choice(responses)
    else:
        resp = responses
        
    await update.message.reply_text(f"🤡 *AGENT FUMBL:* {resp}\n\n_{get_text(lang, 'mood_responses', mood=stats['mood_level'])}_")

def main():
    db.init_db()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("FUMBL Agent started.")
    application.run_polling()

if __name__ == "__main__":
    main()
