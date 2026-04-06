import random

TEXTS = {
    "en": {
        "buttons": {
            "signal": "📈 SIGNAL", "fumble": "🤡 FUMBLE", "portfolio": "💰 PORTFOLIO",
            "price": "💵 PRICE", "holders": "👥 HOLDERS", "balance": "🔍 BALANCE",
            "meme": "🖼️ MEME", "sticker": "🎨 STICKER", "leaderboard": "🏆 TOP LOSERS",
            "language_menu": "🌐 LANGUAGE", "subscribe": "🔔 SUBSCRIBE", "unsubscribe": "🔕 UNSUBSCRIBE",
            "buy": "🚀 BUY $FUMBL", "site": "🌍 SITE", "chat": "💬 CHAT", "help": "❓ HELP",
            "referral_btn": "🤝 REFERRAL", "share_btn": "📤 SHARE SHAME"
        },
        "ranks": [
            "Paper Hands", "Exit Liquidity", "Bag Holder", "Shitcoin Enthusiast", 
            "Professional Loser", "Market Liquidity", "Rug Pull Victim", "Clown Prince", 
            "Zero Balance King", "Eternal Degen"
        ],
        "welcome_new": [
            "Oh, look who it is. Another victim of FOMO. Welcome to the exit liquidity simulator.",
            "Welcome, paper hands. I hope you're ready to see your portfolio go to zero.",
            "Ah, a new clown in our circus. Don't worry, we have plenty of red candles for you."
        ],
        "welcome_old": [
            "Back for more pain? I respect the commitment to losing money.",
            "You're still here? I thought you'd be living under a bridge by now.",
            "Welcome back, Sir Loss-a-Lot. The market missed your donations."
        ],
        "signal_pause": [
            "Analyzing your past failures...",
            "Consulting the magic 8-ball (it's always red)...",
            "Waiting for the whale to dump on you..."
        ],
        "signal": [
            "BUY THE TOP! It's the only way to ensure maximum pain.",
            "SELL NOW! Panic is your only friend.",
            "HODL! Until it's worth exactly zero.",
            "LEVERAGE 100x! Go big or go to the food bank."
        ],
        "signal_rare": [
            "🚨 ALPHA: Go outside and touch grass. Your portfolio is dead anyway.",
            "🚨 INSIDER: The dev just bought a Lambo with your money."
        ],
        "fumble_question": [
            "How much did you lose on that last rug pull?",
            "What's your favorite color of candle? (We only have red)",
            "Why do you keep doing this to yourself?"
        ],
        "fumble_options": ["Too much", "Everything", "My wife left me", "I like the pain"],
        "fumble_result_high": [
            "Impressive. You're a natural-born loser. A true FUMBL legend.",
            "Your ability to lose money is almost a superpower. Disgusting."
        ],
        "fumble_result_medium": [
            "Not bad, but you can lose more. I believe in your incompetence.",
            "A solid effort in failure. Keep trying, the bottom is near."
        ],
        "fumble_result_low": [
            "You're not even good at failing. How pathetic.",
            "Are you even trying to lose money? Try harder."
        ],
        "portfolio_no_wallet": "You haven't even linked a wallet yet. Even your poverty is disorganized.",
        "lang_changed": "Language changed to English. Now you can understand your losses better.",
        "ignore_text": [
            "Stop talking and go buy a high-risk meme coin.",
            "I don't speak 'poor'. Go make some bad trades.",
            "Is that a request for more pain? Just press the buttons."
        ],
        "return_hook": "Back to the menu, clown. There's more money to lose."
    },
    "ru": {
        "buttons": {
            "signal": "📈 СИГНАЛ", "fumble": "🤡 ФАМБЛ", "portfolio": "💰 ПОРТФЕЛЬ",
            "price": "💵 ЦЕНА", "holders": "👥 ХОЛДЕРЫ", "balance": "🔍 БАЛАНС",
            "meme": "🖼️ МЕМ", "sticker": "🎨 СТИКЕР", "leaderboard": "🏆 ТОП ЛУЗЕРОВ",
            "language_menu": "🌐 ЯЗЫК", "subscribe": "🔔 ПОДПИСАТЬСЯ", "unsubscribe": "🔕 ОТПИСАТЬСЯ",
            "buy": "🚀 КУПИТЬ $FUMBL", "site": "🌍 САЙТ", "chat": "💬 ЧАТ", "help": "❓ ПОМОЩЬ",
            "referral_btn": "🤝 ПАРТНЕРКА", "share_btn": "📤 ПОДЕЛИТЬСЯ ПОЗОРОМ"
        },
        "ranks": [
            "Слабые Ручки", "Выходная Ликвидность", "Холдер Пакетов", "Любитель Щиткоинов", 
            "Профессиональный Лузер", "Ликвидность для Рынка", "Жертва Рагпулла", "Принц Клоунов", 
            "Король Нулевого Баланса", "Вечный Деген"
        ],
        "welcome_new": [
            "О, посмотрите, кто пришел. Очередная жертва FOMO. Добро пожаловать в симулятор ликвидности на выходе.",
            "Добро пожаловать, 'бумажные руки'. Надеюсь, ты готов увидеть, как твой портфель обнуляется.",
            "А, новый клоун в нашем цирке. Не волнуйся, у нас полно красных свечей для тебя."
        ],
        "welcome_old": [
            "Вернулся за новой порцией боли? Уважаю твое стремление терять деньги.",
            "Ты всё еще здесь? Я думал, ты уже живешь под мостом.",
            "С возвращением, Сэр Лосс-а-Лот. Рынок скучал по твоим пожертвованиям."
        ],
        "signal_pause": [
            "Анализирую твои прошлые провалы...",
            "Консультируюсь с магическим шаром (он всегда красный)...",
            "Жду, пока кит сольет на тебя свои токены..."
        ],
        "signal": [
            "ПОКУПАЙ НА ХАЯХ! Это единственный способ обеспечить максимум боли.",
            "ПРОДАВАЙ СЕЙЧАС! Паника — твой единственный друг.",
            "ХОДЛ! Пока это не будет стоить ровно ноль.",
            "ПЛЕЧО 100x! Либо пан, либо в столовую для бедных."
        ],
        "signal_rare": [
            "🚨 АЛЬФА: Иди погуляй и потрогай траву. Твой портфель всё равно мертв.",
            "🚨 ИНСАЙД: Разраб только что купил Ламбу на твои деньги."
        ],
        "fumble_question": [
            "Сколько ты потерял на последнем рагпулле?",
            "Какой твой любимый цвет свечи? (У нас только красный)",
            "Зачем ты продолжаешь это делать с собой?"
        ],
        "fumble_options": ["Слишком много", "Всё", "Жена ушла", "Мне нравится боль"],
        "fumble_result_high": [
            "Впечатляет. Ты прирожденный неудачник. Настоящая легенда FUMBL.",
            "Твоя способность терять деньги — это почти суперсила. Отвратительно."
        ],
        "fumble_result_medium": [
            "Неплохо, но ты можешь терять больше. Я верю в твою некомпетентность.",
            "Солидная попытка провала. Продолжай в том же духе, дно близко."
        ],
        "fumble_result_low": [
            "Ты даже в провалах не очень. Как жалко.",
            "Ты вообще пытаешься терять деньги? Старайся лучше."
        ],
        "portfolio_no_wallet": "Ты даже кошелек не привязал. Даже твоя нищета не организована.",
        "lang_changed": "Язык изменен на русский. Теперь ты сможешь лучше понимать свои убытки.",
        "ignore_text": [
            "Хватит болтать, иди купи какой-нибудь щиткоин.",
            "Я не говорю на 'нищебродском'. Иди сделай пару плохих сделок.",
            "Это просьба о новой порции боли? Просто жми на кнопки."
        ],
        "return_hook": "Назад в меню, клоун. Еще не все деньги потеряны."
    }
}

def get_text(lang, key, index=None, mood=None):
    lang_dict = TEXTS.get(lang, TEXTS["en"])
    if key == "ranks" and index is not None:
        ranks = lang_dict.get("ranks", [])
        return ranks[min(index, len(ranks)-1)]
    
    content = lang_dict.get(key, TEXTS["en"].get(key, key))
    if isinstance(content, list):
        return random.choice(content)
    return content

def add_hooks(lang, text):
    hooks = [" 🤡", " 📉", " 💀", " 💸"]
    return text + random.choice(hooks)
