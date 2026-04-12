import os
import logging
import threading

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def run_bot():
    from bot import main as bot_main
    bot_main()

if __name__ == "__main__":
    logger.info("🚀 Starting BINTY Agent (bot only)...")
    run_bot()