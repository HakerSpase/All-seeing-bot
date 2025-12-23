"""
Пакет обработчиков.
"""

from handlers.commands import router as commands_router, set_storage_manager as set_commands_storage
from handlers.business import router as business_router, set_storage_manager as set_business_storage


def set_storage_manager(manager):
    """Установить менеджер хранилища для всех обработчиков."""
    set_commands_storage(manager)
    set_business_storage(manager)
