import os
import threading
import logging
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== ЗАПУСК БОТА ====================
def run_bot():
    """Запускает Telegram бота"""
    from bot import main as bot_main
    bot_main()

# ==================== ЗАПУСК АДМИНКИ ====================
def run_admin():
    """Запускает Flask админку"""
    from admin import app
    port = int(os.environ.get("PORT", 5000))
    
    # Простой health-check handler
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"BINTY Admin is running")
        def log_message(self, format, *args):
            pass
    
    # Запускаем Flask в отдельном потоке
    def start_flask():
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    logger.info(f"✅ Admin started on port {port}")
    
    # Держим поток alive
    flask_thread.join()

# ==================== MAIN ====================
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "admin":
        # Запуск только админки
        run_admin()
    elif len(sys.argv) > 1 and sys.argv[1] == "bot":
        # Запуск только бота
        run_bot()
    else:
        # Запуск обоих
        logger.info("🚀 Starting BINTY Agent (Bot + Admin)...")
        
        # Запускаем бота в основном потоке (он блокирующий)
        # Админку запускаем в отдельном потоке
        admin_thread = threading.Thread(target=run_admin, daemon=True)
        admin_thread.start()
        
        # Бот в основном потоке
        run_bot()