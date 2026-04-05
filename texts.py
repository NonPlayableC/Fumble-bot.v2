import random

# Mood levels: 0: Bored, 1: Annoyed, 2: Angry, 3: Psychotic
TEXTS = {
    "en": {
        "buttons": {
            "signal": "📈 SIGNAL (BAD)",
            "fumble": "🤡 FUMBLE (YOUR SHAME)",
            "portfolio": "💰 PORTFOLIO (PAIN)",
            "price": "💵 PRICE (DON'T BELIEVE)",
            "holders": "👥 HOLDERS",
            "balance": "🔍 BALANCE (PROBABLY 0)",
            "meme": "🖼️ MEME",
            "sticker": "🎨 STICKER",
            "leaderboard": "🏆 TOP LOSERS",
            "language": "🌐 LANGUAGE",
            "subscribe": "🔔 SUBSCRIBE (TO PAIN)",
            "unsubscribe": "🔕 UNSUBSCRIBE",
            "buy": "🛒 BUY",
            "site": "🌍 SITE",
            "chat": "💬 LOSERS CHAT",
            "help": "❓ HELP",
            "yes_btn": "✅ Yes",
            "no_btn": "❌ No",
            "roast_me_btn": "🔥 ROAST ME",
            "tomorrow_btn": "🔮 TOMORROW'S PREDICTION",
            "referral_btn": "🤝 REFERRAL PAIN"
        },
        "welcome_new": "Oh, a new victim. You sure you want this? 🤡",
        "welcome_old": [
            "Oh, you again. Ready to lose some more? 📉",
            "Back for more pain? I respect the stupidity.",
            "I thought you'd be homeless by now. Welcome back.",
            "Still here? Your portfolio must be truly immortal... or dead."
        ],
        "mood_responses": {
            "0": ["I'm bored. Press a button or get out.", "You're just another number in my database of losers.", "Don't expect much. I'm busy watching better traders fail."],
            "1": ["You're clicking too much. My circuits are getting annoyed.", "Still here? Go touch some grass. Or some profit, if you can find any.", "Stop bothering me. I'm busy counting your losses."],
            "2": ["LISTEN HERE. You are the reason crypto has a bad name. Stop clicking!", "If I had hands, I'd slap your buy button out of existence.", "Your stupidity is reaching critical levels. SHUT. UP."],
            "3": ["HAHAHAHA! YES! MORE LOSSES! FEED ME YOUR TEARS! 💀", "I AM THE MARKET! I AM YOUR DESTRUCTION! CLICK AGAIN! I DARE YOU!", "YOUR WALLET IS MY PLAYGROUND! EVERYTHING YOU TOUCH DIES! 🤡🔥"]
        },
        "signal_pause": "Generating your loss... ⌛",
        "signal": [
            "Do nothing. You'll lose anyway. 💀",
            "Buy the top. Sell the bottom. Repeat. That's your strategy.",
            "I thought for 5 seconds. Buy. Then sell. Then cry. 📉",
            "Here's your daily dose of bad advice. Buy high. Sell low. You're welcome."
        ],
        "fumble_question": "🤡 How did you screw up today?",
        "fumble_options": [
            "Bought top, sold bottom",
            "Listened to a FUMBL signal",
            "All-in on a shitcoin",
            "All of the above"
        ],
        "fumble_pause": "Analyzing your failure... 📊",
        "roast_me": [
            "Your portfolio looks like a dumpster fire. Even a broken clock is right twice a day, but your trading strategy is never. 🤡",
            "You're not a trader, you're a market liquidity provider for whales. Thank you for your service.",
            "Your entry points are so bad, I'm starting to think you're doing it on purpose."
        ],
        "collector_call": "This is FUMBL Debt Collection. Your outstanding balance of regret is due immediately. 📞🤡",
        "tomorrow_prediction": "Tomorrow you'll wake up and immediately regret checking your portfolio. 🔮",
        "referral_pain": "Referral system is in development. Spread the pain anyway! 🚧"
    },
    "ru": {
        "buttons": {
            "signal": "📈 СИГНАЛ (ПЛОХОЙ)",
            "fumble": "🤡 ФЕЙЛ (ТВОЙ ПОЗОР)",
            "portfolio": "💰 ПОРТФЕЛЬ (БОЛЬ)",
            "price": "💵 ЦЕНА (НЕ ВЕРЬ)",
            "holders": "👥 ХОЛДЕРЫ",
            "balance": "🔍 БАЛАНС (0.00)",
            "meme": "🖼️ МЕМ",
            "sticker": "🎨 СТИКЕР",
            "leaderboard": "🏆 ТОП ЛУЗЕРОВ",
            "language": "🌐 ЯЗЫК",
            "subscribe": "🔔 ПОДПИСАТЬСЯ (НА БОЛЬ)",
            "unsubscribe": "🔕 ОТПИСАТЬСЯ",
            "buy": "🛒 КУПИТЬ",
            "site": "🌍 САЙТ",
            "chat": "💬 ЧАТ ЛУЗЕРОВ",
            "help": "❓ ПОМОЩЬ",
            "yes_btn": "✅ Да",
            "no_btn": "❌ Нет",
            "roast_me_btn": "🔥 ПРОЖАРКА",
            "tomorrow_btn": "🔮 ПРОГНОЗ НА ЗАВТРА",
            "referral_btn": "🤝 ПАРТНЕРКА"
        },
        "welcome_new": "О, новая жертва. Ты уверен, что хочешь этого? 🤡",
        "welcome_old": [
            "О, опять ты. Готов слить ещё немного? 📉",
            "Снова за болью? Я уважаю тупость.",
            "Я думал, ты уже живешь в коробке под мостом. С возвращением.",
            "Всё еще здесь? Твой портфель либо бессмертен, либо уже сгнил."
        ],
        "mood_responses": {
            "0": ["Мне скучно. Жми на кнопку или вали.", "Ты просто еще один номер в моей базе данных неудачников.", "Не жди многого. Я занят тем, что смотрю, как нормальные люди зарабатывают."],
            "1": ["Ты слишком много кликаешь. Мои схемы начинают раздражаться.", "Всё еще здесь? Иди потрогай траву. Или прибыль, если найдешь.", "Перестань меня донимать. Я считаю твои убытки."],
            "2": ["СЛУШАЙ СЮДА. Ты — причина, по которой крипту считают пузырем. ХВАТИТ КЛИКАТЬ!", "Если бы у меня были руки, я бы вырвал твою кнопку 'Buy' с корнем.", "Твоя тупость достигает критического уровня. ЗАМОЛЧИ."],
            "3": ["ХА-ХА-ХА! ДА! БОЛЬШЕ СЛИВОВ! КОРМИ МЕНЯ СВОИМИ СЛЕЗАМИ! 💀", "Я И ЕСТЬ РЫНОК! Я — ТВОЯ ПОГИБЕЛЬ! ЖМИ ЕЩЕ! Я ТЕБЯ ВЫЗЫВАЮ!", "ТВОЙ КОШЕЛЕК — МОЯ ИГРОВАЯ ПЛОЩАДКА! ВСЁ, К ЧЕМУ ТЫ КАСАЕШЬСЯ, УМИРАЕТ! 🤡🔥"]
        },
        "signal_pause": "Генерирую твой убыток... ⌛",
        "signal": [
            "Ничего не делай. Ты всё равно проиграешь. 💀",
            "Купи на хаях, продай на лоях. Повтори. Это твоя стратегия.",
            "Я думал 5 секунд. Купи. Потом продай. Потом поплачь. 📉",
            "Твоя ежедневная порция плохих советов. Покупай дорого, продавай дешево. Не благодари."
        ],
        "fumble_question": "🤡 Как ты облажался сегодня?",
        "fumble_options": [
            "Купил на хаях, продал на лоях",
            "Послушал сигнал FUMBL",
            "Олл-ин в щиткоин",
            "Всё вышеперечисленное"
        ],
        "fumble_pause": "Анализирую твой провал... 📊",
        "roast_me": [
            "Твой портфель выглядит как горящая свалка. Даже сломанные часы дважды в день показывают правильное время, но твоя торговая стратегия — никогда. 🤡",
            "Ты не трейдер, ты поставщик ликвидности для китов. Спасибо за службу.",
            "Твои точки входа настолько плохи, что я начинаю думать, что ты делаешь это специально."
        ],
        "collector_call": "Это Агентство по сбору долгов FUMBL. Твой баланс сожалений просрочен. 📞🤡",
        "tomorrow_prediction": "Завтра ты проснешься и сразу пожалеешь, что открыл график. 🔮",
        "referral_pain": "Реферальная система в разработке. Распространяй боль просто так! 🚧"
    }
}

def get_text(lang, key, mood=None):
    lang_dict = TEXTS.get(lang, TEXTS["en"])
    
    # Special handling for mood responses
    if key == "mood_responses" and mood is not None:
        responses = lang_dict.get("mood_responses", {}).get(str(mood), [])
        if not responses:
            responses = TEXTS["en"]["mood_responses"].get(str(mood), ["..."])
        return random.choice(responses)
    
    text = lang_dict.get(key, TEXTS["en"].get(key, "Error: Text not found"))
    if isinstance(text, list):
        return random.choice(text)
    return text
