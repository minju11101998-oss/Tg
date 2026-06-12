"""Профиль игрока и таблица лидеров"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import Database
from gamedata import CLASSES, SLOTS, ITEMS, calc_stats, calc_skills, stats_text
from config import EXP_BASE, EXP_SCALE, MAX_LEVEL
import math


def exp_for_level(level: int) -> int:
    return int(EXP_BASE * (level ** EXP_SCALE))


def progress_bar(current: int, total: int, length: int = 10) -> str:
    filled = round(current / max(total, 1) * length)
    return "█" * filled + "░" * (length - filled)


class ProfileHandler:

    @staticmethod
    async def show(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        db: Database = ctx.bot_data["db"]
        uid = update.effective_user.id
        player = await db.get_player(uid)
        if not player:
            await update.message.reply_text("Сначала /start")
            return
        text, kb = await ProfileHandler._build(db, player)
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)

    @staticmethod
    async def show_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        db: Database = ctx.bot_data["db"]
        uid = query.from_user.id
        player = await db.get_player(uid)
        if not player:
            await query.edit_message_text("Сначала /start")
            return
        text, kb = await ProfileHandler._build(db, player)
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)

    @staticmethod
    async def _build(db: Database, player: dict) -> tuple[str, InlineKeyboardMarkup]:
        uid = player["user_id"]
        equipped = await db.get_equipped(uid)
        stats, skills = calc_stats(player, equipped)
        cls = CLASSES[player["class_id"]]

        lvl = player["level"]
        exp = player["exp"]
        exp_need = exp_for_level(lvl) if lvl < MAX_LEVEL else 0
        exp_bar = progress_bar(exp, exp_need) if exp_need else "MAX"

        # Экипированные предметы
        equip_lines = []
        for slot, slot_name in SLOTS.items():
            item_id = equipped.get(slot)
            if item_id and item_id in ITEMS:
                equip_lines.append(f"{slot_name}: *{ITEMS[item_id]['name']}*")
            else:
                equip_lines.append(f"{slot_name}: _пусто_")

        wl = f"{player['wins']}W / {player['losses']}L"
        total = player["wins"] + player["losses"]
        wr = f"{round(player['wins']/total*100)}%" if total > 0 else "—"

        text = (
            f"👤 *{player['first_name']}* {cls['emoji']}{cls['name']}\n"
            f"⭐ Уровень *{lvl}*  |  🏆 {wl}  |  📊 {wr}\n"
            f"✨ Опыт: `{exp_bar}` {exp}/{exp_need if exp_need else '∞'}\n"
            f"💰 Золото: *{player['gold']}*\n\n"
            f"*── Экипировка ──*\n"
            + "\n".join(equip_lines)
            + f"\n\n*── Статы ──*\n"
            + stats_text(stats, skills)
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Магазин", callback_data="slot:weapon"),
             InlineKeyboardButton("🎒 Инвентарь", callback_data="inventory")],
            [InlineKeyboardButton("⚔️ В Арену", callback_data="arena")],
        ])
        return text, kb

    @staticmethod
    async def leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        db: Database = ctx.bot_data["db"]
        rows = await db.get_leaderboard(10)
        if not rows:
            await update.message.reply_text("Таблица пуста.")
            return
        medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 10
        lines = ["🏆 *ТОП-10 АРЕНЫ*\n"]
        for i, r in enumerate(rows):
            name = r["first_name"] or r["username"] or "Игрок"
            total = r["wins"] + r["losses"]
            wr = f"{round(r['wins']/total*100)}%" if total else "—"
            lines.append(
                f"{medals[i]} {i+1}. *{name}* — Ур.{r['level']} | "
                f"{r['wins']}W | {wr}"
            )
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
