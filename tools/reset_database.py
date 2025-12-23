"""
Утилита сброса базы данных.
Удаляет все сообщения из Supabase.
"""

from database import supabase


def reset_db():
    """Очистить таблицу сообщений."""
    print("ВНИМАНИЕ: Это удалит ВСЕ сообщения из базы данных Supabase.")
    print("Таблицы owners и users останутся нетронутыми.")
    confirm = input("Введите 'DELETE' для подтверждения: ")
    
    if confirm == "DELETE":
        try:
            print("Удаление сообщений...")
            res = supabase.table("messages").delete().neq("message_id", -1).execute()
            count = len(res.data) if res.data else "некоторое количество"
            print(f"Успешно! Удалено {count} сообщений.")
        except Exception as e:
            print(f"Ошибка: {e}")
    else:
        print("Отменено.")


if __name__ == "__main__":
    reset_db()
