import asyncio
import json
from supabase_client import init_supabase, set_translation
from texts import TEXTS

async def migrate():
    init_supabase()
    
    for lang, sections in TEXTS.items():
        print(f"Migrating {lang}...")
        
        for key, value in sections.items():
            if key == "buttons":
                # Кнопки
                for btn_key, btn_value in value.items():
                    if isinstance(btn_value, list):
                        btn_value = json.dumps(btn_value)  # Список фраз как JSON
                    await set_translation(lang, f"btn_{btn_key}", btn_value)
            elif isinstance(value, list):
                # Список фраз
                await set_translation(lang, key, json.dumps(value))
            elif isinstance(value, dict):
                # Вложенные словари (например, titles)
                for sub_key, sub_value in value.items():
                    await set_translation(lang, f"{key}_{sub_key}", sub_value)
            else:
                # Обычная строка
                await set_translation(lang, key, str(value))
    
    print("Migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate())