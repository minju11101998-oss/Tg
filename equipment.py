"""Магазин экипировки и управление инвентарём"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import Database
from gamedata import CLASSES, SLOTS, ITEMS, items_by_slot, items_by_slot_all


class EquipmentHandler:

    @staticmethod
    async def show_shop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        db: Database = ctx.bot_data["db"]
        uid = update.effective_user.id
        player = await db.get_player(uid)
        if not player:
            await update.message.reply_text("Сначала /start")
            return
        text, kb = _build_slot_select(player)
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)

    @staticmethod
    async def show_slot(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        db: Database = ctx.bot_data["db"]
        uid = query.from_user.id
        slot = query.data.split(":")[1]
        player = await db.get_player(uid)
        inventory = await db.get_inventory(uid)
        equipped = await db.get_equipped(uid)

        available = items_by_slot_all(slot)
        lvl = player["level"]

        lines = [f"*{SLOTS[slot]}* — выбери предмет:\n"]
        buttons = []

        for iid, item in available:
            owned = iid in inventory
            is_equipped = equipped.get(slot) == iid
            lock = "🔒 " if item["req_level"] > lvl else ""
            tag = " ✅" if is_equipped else (" 📦" if owned else "")
            lines.append(
                f"{lock}*{item['name']}*{tag}\n"
                f"_{item['desc']}_\n"
                f"Требуется: Ур.{item['req_level']}  |  💰 {item['price']}\n"
                + _item_stats_short(item) + "\n"
            )
            row = []
            if not owned and not is_equipped:
                if item["req_level"] <= lvl:
                    row.append(InlineKeyboardButton(
                        f"💰 Купить {item['name']}", callback_data=f"buy:{iid}"
                    ))
            elif owned and not is_equipped:
                row.append(InlineKeyboardButton(
                    f"✅ Надеть {item['name']}", callback_data=f"equip:{iid}"
                ))
            elif is_equipped:
                row.append(InlineKeyboardButton(
                    f"❌ Снять {item['name']}", callback_data=f"unequip:{slot}"
                ))
            if row:
                buttons.append(row)

        buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="inventory")])

        await query.edit_message_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    @staticmethod
    async def buy_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        db: Database = ctx.bot_data["db"]
        uid = query.from_user.id
        item_id = query.data.split(":")[1]

        if item_id not in ITEMS:
            await query.answer("Предмет не найден.", show_alert=True)
            return

        item = ITEMS[item_id]
        player = await db.get_player(uid)

        if player["level"] < item["req_level"]:
            await query.answer(f"Требуется уровень {item['req_level']}!", show_alert=True)
            return
        if await db.has_item(uid, item_id):
            await query.answer("Ты уже владеешь этим предметом!", show_alert=True)
            return
        if player["gold"] < item["price"]:
            await query.answer(f"Недостаточно золота! Нужно {item['price']} 💰", show_alert=True)
            return

        await db.update_player(uid, gold=player["gold"] - item["price"])
        await db.add_to_inventory(uid, item_id)
        await query.answer(f"✅ Куплено: {item['name']}!", show_alert=True)

        # Обновить экран
        slot = item["slot"]
        query.data = f"slot:{slot}"
        await EquipmentHandler.show_slot(update, ctx)

    @staticmethod
    async def equip_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        db: Database = ctx.bot_data["db"]
        uid = query.from_user.id
        item_id = query.data.split(":")[1]

        if item_id not in ITEMS:
            await query.answer("Предмет не найден.", show_alert=True)
            return

        if not await db.has_item(uid, item_id):
            await query.answer("Этого предмета нет в инвентаре!", show_alert=True)
            return

        item = ITEMS[item_id]
        await db.equip_item(uid, item["slot"], item_id)
        await query.answer(f"✅ Надето: {item['name']}")

        query.data = f"slot:{item['slot']}"
        await EquipmentHandler.show_slot(update, ctx)

    @staticmethod
    async def unequip_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        db: Database = ctx.bot_data["db"]
        uid = query.from_user.id
        slot = query.data.split(":")[1]

        await db.unequip_item(uid, slot)
        await query.answer(f"❌ Снято с {SLOTS.get(slot, slot)}")

        query.data = f"slot:{slot}"
        await EquipmentHandler.show_slot(update, ctx)

    @staticmethod
    async def show_inventory(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        db: Database = ctx.bot_data["db"]
        uid = query.from_user.id
        player = await db.get_player(uid)
        if not player:
            await query.edit_message_text("Сначала /start")
            return
        text, kb = _build_slot_select(player)
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)


def _build_slot_select(player: dict) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"🛒 *МАГАЗИН И ЭКИПИРОВКА*\n"
        f"Ур. {player['level']} | 💰 {player['gold']} золота\n\n"
        f"Выбери слот для просмотра:"
    )
    buttons = []
    for slot, slot_name in SLOTS.items():
        buttons.append([InlineKeyboardButton(slot_name, callback_data=f"slot:{slot}")])
    buttons.append([InlineKeyboardButton("👤 Профиль", callback_data="profile")])
    return text, InlineKeyboardMarkup(buttons)


def _item_stats_short(item: dict) -> str:
    stats = item.get("stats", {})
    if not stats:
        return ""
    stat_names = {
        "hp": "❤️", "atk": "🗡", "def": "🔰", "crit_chance": "🥊",
        "crit_power": "💥", "foresight": "👁", "dodge": "⚡️",
        "counter": "🤺", "accuracy": "🎯"
    }
    parts = []
    for k, v in stats.items():
        sym = stat_names.get(k, k)
        sign = "+" if v >= 0 else ""
        parts.append(f"{sym}{sign}{v}")
    return " | ".join(parts)
