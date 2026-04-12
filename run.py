import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def run_health_server():
    """HTTP-сервер для health-check Render (отвечает на порт)"""
    port = int(os.environ.get("PORT", 10000))
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"BINTY is running")
        def log_message(self, format, *args):
            pass
    server = HTTPServer(("0.0.0.0", port), Handler)
    logger.info(f"Health server started on port {port}")
    server.serve_forever()

def run_bot():
    """Запускает Telegram бота"""
    from bot import main as bot_main
    bot_main()

if __name__ == "__main__":
    logger.info("🚀 Starting BINTY Agent...")
    
    # Health-check в отдельном потоке (чтобы Render не убивал сервис)
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    
    # Бот в основном потоке
    run_bot()