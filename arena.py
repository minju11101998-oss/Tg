"""Вход в арену и поиск противника"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import Database
from matchmaking import MatchmakingManager
from handlers.battle import BattleHandler
from config import MATCHMAKING_TIMEOUT


class ArenaHandler:

    @staticmethod
    async def enter(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        db: Database = ctx.bot_data["db"]
        mm: MatchmakingManager = ctx.bot_data["matchmaking"]
        uid = update.effective_user.id
        chat_id = update.effective_chat.id

        player = await db.get_player(uid)
        if not player:
            await update.message.reply_text("Сначала /start")
            return
        if player.get("is_banned"):
            await update.message.reply_text("🚫 Ты забанен.")
            return
        if mm.in_queue(uid):
            await update.message.reply_text("⏳ Ты уже в очереди поиска.")
            return

        opponent_id = await mm.add_to_queue(uid, chat_id)

        if opponent_id:
            # Нашли реального противника
            opp_chat_id = mm.queue.get(opponent_id, {}).get("chat_id") or opponent_id
            await BattleHandler.start_pvp(ctx.application, uid, opponent_id, chat_id, opp_chat_id)
        else:
            # Ждём
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отменить поиск", callback_data="arena_cancel")
            ]])
            await update.message.reply_text(
                f"⚔️ *Поиск противника...*\n\n"
                f"🔍 Ищем реального игрока {MATCHMAKING_TIMEOUT} секунд.\n"
                f"Если никого не найдём — тебя встретит бот-противник.",
                parse_mode="Markdown",
                reply_markup=kb
            )

    @staticmethod
    async def enter_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        db: Database = ctx.bot_data["db"]
        mm: MatchmakingManager = ctx.bot_data["matchmaking"]
        uid = query.from_user.id
        chat_id = query.message.chat_id

        player = await db.get_player(uid)
        if not player:
            await query.edit_message_text("Сначала /start")
            return
        if player.get("is_banned"):
            await query.edit_message_text("🚫 Ты забанен.")
            return
        if mm.in_queue(uid):
            await query.edit_message_text("⏳ Ты уже в очереди поиска.")
            return

        opponent_id = await mm.add_to_queue(uid, chat_id)

        if opponent_id:
            opp_chat_id = mm.queue.get(opponent_id, {}).get("chat_id") or opponent_id
            await query.edit_message_text("⚔️ Противник найден! Бой начинается...")
            await BattleHandler.start_pvp(ctx.application, uid, opponent_id, chat_id, opp_chat_id)
        else:
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отменить поиск", callback_data="arena_cancel")
            ]])
            await query.edit_message_text(
                f"⚔️ *Поиск противника...*\n\n"
                f"🔍 Ищем реального игрока {MATCHMAKING_TIMEOUT} секунд.\n"
                f"Если никого не найдём — бот-противник.",
                parse_mode="Markdown",
                reply_markup=kb
            )

    @staticmethod
    async def cancel_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        mm: MatchmakingManager = ctx.bot_data["matchmaking"]
        uid = update.effective_user.id
        if mm.in_queue(uid):
            mm.remove_from_queue(uid)
            await update.message.reply_text("✅ Поиск отменён.")
        else:
            await update.message.reply_text("Ты не в очереди.")
