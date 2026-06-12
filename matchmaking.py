"""Система поиска противников с таймаутом → бот-заменитель"""

import asyncio
import logging
from config import MATCHMAKING_TIMEOUT

logger = logging.getLogger(__name__)


class MatchmakingManager:
    def __init__(self, app):
        self.app = app
        self.queue: dict[int, dict] = {}  # user_id → {chat_id, message_id, task}

    def in_queue(self, user_id: int) -> bool:
        return user_id in self.queue

    async def add_to_queue(self, user_id: int, chat_id: int) -> int | None:
        """
        Добавить игрока в очередь.
        Если уже есть кто-то → сразу матч → вернуть opponent_id.
        Если нет → запустить таймер → вернуть None (ждём).
        """
        # Найти ожидающего реального игрока
        for waiting_id, info in list(self.queue.items()):
            if waiting_id != user_id:
                # Матч найден!
                self._cancel_timer(waiting_id)
                del self.queue[waiting_id]
                return waiting_id  # реальный противник

        # Никого нет — добавить в очередь с таймером
        task = asyncio.create_task(
            self._timeout_task(user_id, chat_id)
        )
        self.queue[user_id] = {"chat_id": chat_id, "task": task}
        return None

    async def _timeout_task(self, user_id: int, chat_id: int):
        """После таймаута матч с ботом"""
        await asyncio.sleep(MATCHMAKING_TIMEOUT)
        if user_id in self.queue:
            del self.queue[user_id]
            # Уведомить через BattleHandler
            from handlers.battle import BattleHandler
            await BattleHandler.start_vs_bot(self.app, user_id, chat_id)

    def remove_from_queue(self, user_id: int):
        if user_id in self.queue:
            self._cancel_timer(user_id)
            del self.queue[user_id]

    def _cancel_timer(self, user_id: int):
        info = self.queue.get(user_id)
        if info and "task" in info:
            info["task"].cancel()

    def queue_size(self) -> int:
        return len(self.queue)
