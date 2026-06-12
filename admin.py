"""Панель администратора"""

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import Database
from config import ADMIN_IDS


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


class AdminHandler:

    # ── Главная панель ──────────────────────────────────────────────────────

    @staticmethod
    async def panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("🚫 Нет доступа.")
            return
        db: Database = ctx.bot_data["db"]
        mm = ctx.bot_data["matchmaking"]
        text, kb = await AdminHandler._build_panel(db, mm)
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)

    @staticmethod
    async def panel_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if not is_admin(query.from_user.id):
            return
        db: Database = ctx.bot_data["db"]
        mm = ctx.bot_data["matchmaking"]
        action = query.data.split(":")[1]

        if action == "main":
            text, kb = await AdminHandler._build_panel(db, mm)
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)

        elif action == "players":
            rows = await db.get_leaderboard(20)
            lines = ["👥 *Все игроки:*\n"]
            for r in rows:
                name = r["first_name"] or r["username"] or str(r["user_id"])
                lines.append(f"• `{r['user_id']}` *{name}* — Ур.{r['level']} | {r['wins']}W/{r['losses']}L")
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="admin:main")
            ]])
            await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=kb)

        elif action == "broadcast_start":
            ctx.user_data["admin_action"] = "broadcast"
            await query.edit_message_text(
                "📢 *Рассылка*\n\nНапиши текст сообщения для всех игроков:",
                parse_mode="Markdown"
            )

    @staticmethod
    async def _build_panel(db, mm) -> tuple[str, InlineKeyboardMarkup]:
        total = await db.count_players()
        battles = await db.count_battles()
        queue = mm.queue_size()
        text = (
            "🔧 *ПАНЕЛЬ АДМИНИСТРАТОРА*\n\n"
            f"👥 Игроков: *{total}*\n"
            f"⚔️ Боёв проведено: *{battles}*\n"
            f"🔍 В очереди сейчас: *{queue}*\n\n"
            "*Команды:*\n"
            "/give_gold [user_id] [amount] — выдать золото\n"
            "/ban [user_id] — забанить\n"
            "/unban [user_id] — разбанить\n"
            "/broadcast [текст] — рассылка всем\n"
            "/set_level [user_id] [level] — установить уровень\n"
            "/stats — статистика бота"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 Список игроков", callback_data="admin:players")],
            [InlineKeyboardButton("📢 Рассылка", callback_data="admin:broadcast_start")],
        ])
        return text, kb

    # ── Команды ─────────────────────────────────────────────────────────────

    @staticmethod
    async def give_gold(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("🚫 Нет доступа.")
            return
        args = ctx.args
        if len(args) < 2:
            await update.message.reply_text("Использование: /give_gold [user_id] [amount]")
            return
        try:
            target_id = int(args[0])
            amount = int(args[1])
        except ValueError:
            await update.message.reply_text("Неверные параметры.")
            return

        db: Database = ctx.bot_data["db"]
        player = await db.get_player(target_id)
        if not player:
            await update.message.reply_text("Игрок не найден.")
            return
        await db.update_player(target_id, gold=player["gold"] + amount)
        await update.message.reply_text(f"✅ Выдано {amount} золота игроку `{target_id}`.", parse_mode="Markdown")
        try:
            await ctx.bot.send_message(target_id, f"🎁 Администратор выдал тебе *{amount}* золота!", parse_mode="Markdown")
        except:
            pass

    @staticmethod
    async def ban_user(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            return
        args = ctx.args
        if not args:
            await update.message.reply_text("Использование: /ban [user_id]")
            return
        try:
            target_id = int(args[0])
        except ValueError:
            await update.message.reply_text("Неверный user_id.")
            return
        db: Database = ctx.bot_data["db"]
        await db.update_player(target_id, is_banned=1)
        await update.message.reply_text(f"🚫 Игрок `{target_id}` забанен.", parse_mode="Markdown")

    @staticmethod
    async def unban_user(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            return
        args = ctx.args
        if not args:
            await update.message.reply_text("Использование: /unban [user_id]")
            return
        try:
            target_id = int(args[0])
        except ValueError:
            await update.message.reply_text("Неверный user_id.")
            return
        db: Database = ctx.bot_data["db"]
        await db.update_player(target_id, is_banned=0)
        await update.message.reply_text(f"✅ Игрок `{target_id}` разбанен.", parse_mode="Markdown")

    @staticmethod
    async def bot_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            return
        db: Database = ctx.bot_data["db"]
        mm = ctx.bot_data["matchmaking"]
        total = await db.count_players()
        battles = await db.count_battles()
        queue = mm.queue_size()
        await update.message.reply_text(
            f"📊 *Статистика бота:*\n\n"
            f"👥 Всего игроков: *{total}*\n"
            f"⚔️ Всего боёв: *{battles}*\n"
            f"🔍 В очереди: *{queue}*",
            parse_mode="Markdown"
        )

    @staticmethod
    async def set_level(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            return
        args = ctx.args
        if len(args) < 2:
            await update.message.reply_text("Использование: /set_level [user_id] [level]")
            return
        try:
            target_id = int(args[0])
            level = int(args[1])
        except ValueError:
            await update.message.reply_text("Неверные параметры.")
            return
        if level < 1 or level > 50:
            await update.message.reply_text("Уровень: 1–50")
            return
        db: Database = ctx.bot_data["db"]
        await db.update_player(target_id, level=level, exp=0)
        await update.message.reply_text(f"✅ Уровень `{target_id}` установлен: *{level}*.", parse_mode="Markdown")

    # ── Рассылка ─────────────────────────────────────────────────────────────

    @staticmethod
    async def broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            return
        text = " ".join(ctx.args)
        if not text:
            await update.message.reply_text("Использование: /broadcast [текст]")
            return
        ctx.user_data["broadcast_text"] = text
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Отправить", callback_data="broadcast_confirm"),
            InlineKeyboardButton("❌ Отмена", callback_data="admin:main"),
        ]])
        await update.message.reply_text(
            f"📢 *Предпросмотр рассылки:*\n\n{text}\n\nОтправить всем игрокам?",
            parse_mode="Markdown", reply_markup=kb
        )

    @staticmethod
    async def handle_broadcast_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            return
        if ctx.user_data.get("admin_action") != "broadcast":
            return
        text = update.message.text
        ctx.user_data["broadcast_text"] = text
        ctx.user_data["admin_action"] = None
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Отправить", callback_data="broadcast_confirm"),
            InlineKeyboardButton("❌ Отмена", callback_data="admin:main"),
        ]])
        await update.message.reply_text(
            f"📢 *Предпросмотр:*\n\n{text}\n\nОтправить?",
            parse_mode="Markdown", reply_markup=kb
        )

    @staticmethod
    async def confirm_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if not is_admin(query.from_user.id):
            return
        text = ctx.user_data.get("broadcast_text", "")
        if not text:
            await query.edit_message_text("Текст не найден.")
            return
        db: Database = ctx.bot_data["db"]
        players = await db.get_all_players()
        sent = 0
        failed = 0
        for p in players:
            try:
                await ctx.bot.send_message(p["user_id"], f"📢 *Объявление:*\n\n{text}", parse_mode="Markdown")
                sent += 1
                await asyncio.sleep(0.05)
            except:
                failed += 1
        await query.edit_message_text(
            f"✅ Рассылка завершена!\n\n📤 Отправлено: *{sent}*\n❌ Ошибок: *{failed}*",
            parse_mode="Markdown"
        )
