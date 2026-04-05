# 🤡 FUMBL Telegram Bot v2.0

The ultimate "loss-tracking" bot for crypto degens. Now with a cleaner interface and more toxic roasts.

## 🚀 Features

1.  **Single Message Interface**: No more chat spam. The bot edits its own messages to provide a clean, app-like experience.
2.  **Toxic Roasts & Predictions**: Daily doses of pain and "tomorrow's failure" predictions.
3.  **Real-time Price Tracking**: Integrated with DexScreener API.
4.  **Portfolio Visualizer**: Generates "loss charts" using Pillow.
5.  **Multi-language Support**: English, Russian, Spanish, and Chinese.
6.  **Partner Program (Ready-to-use)**: Referral system implemented with DB tracking, ready for rewards.
7.  **Admin Panel**: Separate web interface for monitoring stats and users.

## 🛠 Installation

1.  **Install dependencies**:
    ```bash
    pip install python-telegram-bot aiohttp pillow flask
    ```

2.  **Set environment variables**:
    ```bash
    export TELEGRAM_BOT_TOKEN="your_bot_token"
    export TOKEN_ADDRESS="your_solana_token_address"
    export ADMIN_ID="your_telegram_user_id"
    export ADMIN_PASSWORD="your_admin_password"
    ```

3.  **Run the bot**:
    ```bash
    python main_v2.py
    ```

4.  **Run the admin panel (optional)**:
    ```bash
    python admin_panel.py
    ```

## 📁 Project Structure

- `main_v2.py`: The core bot logic (handlers, interface, UI).
- `database.py`: SQLite wrapper for users, fumbles, and referrals.
- `texts.py`: The "brain" of the bot, containing all toxic content and translations.
- `admin_panel.py`: Separate Flask web application for administration.
- `twitter_poster.py`: Scheduled task for posting fumbles to X/Twitter.

## 🤡 FUMBL Strategy

The goal of this bot is **virality through provocation**. Don't make it useful. Make it funny, mean, and addictive.

- Use the `/admin` command in Telegram for quick stats.
- Use the web panel at `http://localhost:5000` for deep user analysis.

---
*Created with pain for FUMBL Community.*
