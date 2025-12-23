"""
Утилита скачивания файлов по file_id.
Использует токен бота для загрузки.
"""

import asyncio
import os
from aiogram import Bot
from config import TOKEN


async def main():
    """Основной цикл программы."""
    print("=== Скачивание файлов по file_id ===")
    print("Токен загружен из .env\n")
    
    try:
        bot = Bot(token=TOKEN)
    except Exception as e:
        print(f"Ошибка инициализации бота: {e}")
        return

    print("Бот инициализирован успешно.\n")
    
    while True:
        file_id = input("Введите file_id (или 'q' для выхода): ").strip()
        if file_id.lower() == 'q':
            break
            
        if not file_id:
            continue

        try:
            print(f"Получаю информацию о файле: {file_id}")
            file_info = await bot.get_file(file_id)
            
            file_path = file_info.file_path
            file_name = os.path.basename(file_path)
            
            # Папка для скачивания
            download_dir = "downloads"
            os.makedirs(download_dir, exist_ok=True)
            
            destination = os.path.join(download_dir, file_name)
            
            print(f"Скачиваю в {destination}...")
            await bot.download_file(file_path, destination)
            print(f"Готово! Сохранено в {destination}\n")
            
        except Exception as e:
            print(f"Ошибка скачивания: {e}\n")

    await bot.session.close()
    print("До свидания!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nВыход...")
