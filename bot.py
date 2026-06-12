"""
╔══════════════════════════════════════════╗
║   ⚔️  ARENA BATTLE  ⚔️                   ║
║   Telegram PvP RPG Bot                   ║
║   Запуск: python bot.py                  ║
╚══════════════════════════════════════════╝

pip install python-telegram-bot==20.7 aiosqlite
"""

import logging
import asyncio
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from telegram import Update

from config import BOT_TOKEN, ADMIN_IDS
from database import Database
from handlers.start import StartHandler
from handlers.arena import ArenaHandler
from handlers.equipment import EquipmentHandler
from handlers.profile import ProfileHandler
from handlers.admin import AdminHandler
from handlers.battle import BattleHandler
from matchmaking import MatchmakingManager

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def post_init(app: Application):
    app.bot_data["db"] = Database()
    await app.bot_data["db"].init()
    app.bot_data["matchmaking"] = MatchmakingManager(app)
    logger.info("✅ База данных инициализирована")


def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # ── Start / Profile ──
    app.add_handler(CommandHandler("start", StartHandler.handle))
    app.add_handler(CommandHandler("profile", ProfileHandler.show))
    app.add_handler(CommandHandler("top", ProfileHandler.leaderboard))

    # ── Arena ──
    app.add_handler(CommandHandler("arena", ArenaHandler.enter))
    app.add_handler(CommandHandler("cancel", ArenaHandler.cancel_search))

    # ── Equipment ──
    app.add_handler(CommandHandler("equipment", EquipmentHandler.show_shop))

    # ── Admin ──
    app.add_handler(CommandHandler("admin", AdminHandler.panel))
    app.add_handler(CommandHandler("give_gold", AdminHandler.give_gold))
    app.add_handler(CommandHandler("ban", AdminHandler.ban_user))
    app.add_handler(CommandHandler("unban", AdminHandler.unban_user))
    app.add_handler(CommandHandler("broadcast", AdminHandler.broadcast))
    app.add_handler(CommandHandler("stats", AdminHandler.bot_stats))
    app.add_handler(CommandHandler("set_level", AdminHandler.set_level))

    # ── Callbacks ──
    app.add_handler(CallbackQueryHandler(StartHandler.class_select, pattern="^class:"))
    app.add_handler(CallbackQueryHandler(EquipmentHandler.buy_item, pattern="^buy:"))
    app.add_handler(CallbackQueryHandler(EquipmentHandler.equip_item, pattern="^equip:"))
    app.add_handler(CallbackQueryHandler(EquipmentHandler.unequip_item, pattern="^unequip:"))
    app.add_handler(CallbackQueryHandler(EquipmentHandler.show_slot, pattern="^slot:"))
    app.add_handler(CallbackQueryHandler(EquipmentHandler.show_inventory, pattern="^inventory$"))
    app.add_handler(CallbackQueryHandler(BattleHandler.action, pattern="^battle:"))
    app.add_handler(CallbackQueryHandler(ArenaHandler.enter_cb, pattern="^arena$"))
    app.add_handler(CallbackQueryHandler(ProfileHandler.show_cb, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(AdminHandler.panel_cb, pattern="^admin:"))
    app.add_handler(CallbackQueryHandler(AdminHandler.confirm_broadcast, pattern="^broadcast_confirm$"))

    # ── Text (admin broadcast) ──
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, AdminHandler.handle_broadcast_text
    ))

    logger.info("⚔️  Arena Bot запущен!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
