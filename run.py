import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def run_admin():
    """Запускает Flask админку на порту Render (PORT)"""
    from admin import app
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def run_bot():
    """Запускает Telegram бота"""
    from bot import main as bot_main
    bot_main()

if __name__ == "__main__":
    logger.info("🚀 Starting BINTY Agent...")
    
    # Админка в отдельном потоке (на порту PORT)
    admin_thread = threading.Thread(target=run_admin, daemon=True)
    admin_thread.start()
    
    # Бот в основном потоке (блокирующий)
    run_bot()