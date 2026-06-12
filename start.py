"""Регистрация нового игрока и выбор класса"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import Database
from gamedata import CLASSES, calc_stats, calc_skills, stats_text
from config import EXP_BASE


class StartHandler:

    @staticmethod
    async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        db: Database = ctx.bot_data["db"]
        uid = update.effective_user.id

        player = await db.get_player(uid)
        if player:
            await update.message.reply_text(
                f"С возвращением, *{player['first_name']}*! ⚔️\n"
                "Ты уже в Арене. Используй /profile или /arena.",
                parse_mode="Markdown"
            )
            return

        # Новый игрок — выбор класса
        text = (
            "⚔️ *ДОБРО ПОЖАЛОВАТЬ В АРЕНУ* ⚔️\n\n"
            "Выбери свой класс — он определяет рост навыков:\n\n"
        )
        for cid, cls in CLASSES.items():
            text += (
                f"{cls['name']}\n"
                f"_{cls['desc']}_\n"
                f"✊{cls['strength']} ♥️{cls['endurance']} 💫{cls['agility']} 🧿{cls['intuition']}\n"
                f"🔑 Умение: *{cls['skill']}* — {cls['skill_desc']}\n\n"
            )

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(CLASSES[c]["name"], callback_data=f"class:{c}")]
            for c in CLASSES
        ])
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)

    @staticmethod
    async def class_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        db: Database = ctx.bot_data["db"]
        uid = query.from_user.id
        class_id = query.data.split(":")[1]

        # Проверка — вдруг уже зарегистрирован
        if await db.get_player(uid):
            await query.edit_message_text("Ты уже зарегистрирован! /profile")
            return

        username = query.from_user.username or ""
        first_name = query.from_user.first_name or "Воин"
        await db.create_player(uid, username, first_name, class_id)

        cls = CLASSES[class_id]
        fake_player = {"level": 1, "class_id": class_id}
        stats, skills = calc_stats(fake_player, {})

        await query.edit_message_text(
            f"✅ Класс выбран: *{cls['name']}*\n\n"
            f"{stats_text(stats, skills)}\n\n"
            f"💰 Начальное золото: *200*\n\n"
            f"Используй:\n"
            f"/arena — поиск боя\n"
            f"/equipment — магазин экипировки\n"
            f"/profile — твой профиль\n"
            f"/top — таблица лидеров",
            parse_mode="Markdown"
        )
