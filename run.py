import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def run_health_server():
    """HTTP сервер для health-check Render"""
    port = int(os.environ.get("PORT", 8000))
    
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"BINTY is running")
        def log_message(self, format, *args):
            pass
    
    server = HTTPServer(("0.0.0.0", port), Handler)
    logger.info(f"✅ Health server on port {port}")
    server.serve_forever()

def run_admin():
    """Запускает Flask админку"""
    from admin import app
    port = int(os.environ.get("ADMIN_PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def run_bot():
    """Запускает Telegram бота"""
    from bot import main as bot_main
    bot_main()

if __name__ == "__main__":
    logger.info("🚀 Starting BINTY Agent (Bot + Admin + Health)...")
    
    # Health-check сервер (для Render)
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    
    # Админка в отдельном потоке
    admin_thread = threading.Thread(target=run_admin, daemon=True)
    admin_thread.start()
    
    # Бот в основном потоке (блокирующий)
    run_bot()