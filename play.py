import threading
import subprocess
import sys
import os

# --- Настройка путей к твоим файлам ---
# Укажи точные имена твоих файлов, если они отличаются
BOT_SCRIPT = "main_v2.py"      # ← Твой файл с ботом
ADMIN_SCRIPT = "admin_panel.py"   # ← Твой файл с админкой

def run_script(script_name):
    """Функция для запуска Python-скрипта в отдельном процессе."""
    print(f"🚀 Запускаю {script_name}...")
    try:
        # Запускаем скрипт в новом процессе
        # Используем sys.executable для корректного вызова интерпретатора Python
        process = subprocess.Popen([sys.executable, script_name])
        process.wait()  # Ждем завершения процесса (в норме не должно случиться)
    except Exception as e:
        print(f"❌ Ошибка при запуске {script_name}: {e}")

if __name__ == "__main__":
    print("🔄 Launchpad активирован. Запускаю бота и админ-панель...")

    # Создаём потоки для бота и админки
    bot_thread = threading.Thread(target=run_script, args=(BOT_SCRIPT,), name="BotThread")
    admin_thread = threading.Thread(target=run_script, args=(ADMIN_SCRIPT,), name="AdminThread")

    # Запускаем оба потока
    bot_thread.start()
    admin_thread.start()

    # Ожидаем завершения работы потоков (они будут работать бесконечно)
    bot_thread.join()
    admin_thread.join()

    print("🛑 Оба сервиса остановлены.")