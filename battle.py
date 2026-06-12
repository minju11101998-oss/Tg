"""
Боевая система Арены
Пошаговый бой: реальный игрок vs реальный или vs бот-заменитель
"""

import asyncio
import random
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram import Update
from database import Database
from gamedata import CLASSES, ITEMS, calc_stats, calc_skills
from config import (
    ARENA_WIN_GOLD, ARENA_LOSS_GOLD,
    ARENA_WIN_EXP, ARENA_LOSS_EXP,
    EXP_BASE, EXP_SCALE, MAX_LEVEL, TURN_TIMEOUT
)
import math

logger = logging.getLogger(__name__)

# Активные бои: battle_id → BattleState
active_battles: dict[str, "BattleState"] = {}


def exp_for_level(level: int) -> int:
    return int(EXP_BASE * (level ** EXP_SCALE))


# ─── BOT OPPONENT ──────────────────────────────────────────────────────────────

BOT_NAMES = [
    "Теневой страж", "Арена-Голем", "Красный клинок",
    "Хаос-Берсерк", "Призрак войны", "Стальной мститель"
]

def make_bot_opponent(level: int) -> dict:
    """Создать бота-противника под уровень игрока"""
    name = random.choice(BOT_NAMES)
    cls = random.choice(list(CLASSES.keys()))
    fake = {"level": max(1, level + random.randint(-1, 1)), "class_id": cls}
    stats, skills = calc_stats(fake, {})
    # Небольшой рандом
    stats["hp"] = int(stats["hp"] * random.uniform(0.9, 1.1))
    stats["atk"] = int(stats["atk"] * random.uniform(0.9, 1.1))
    return {
        "user_id": 0,
        "first_name": f"🤖 {name}",
        "class_id": cls,
        "level": fake["level"],
        "is_bot": True,
        "stats": stats,
        "skills": skills,
    }


# ─── BATTLE STATE ──────────────────────────────────────────────────────────────

class BattleState:
    def __init__(
        self, battle_id: str,
        p1_id: int, p1_chat: int, p1_data: dict,
        p2_id: int, p2_chat: int | None, p2_data: dict,
        is_bot: bool = False
    ):
        self.battle_id = battle_id
        self.is_bot = is_bot
        self.round = 1

        self.p1 = {
            "id": p1_id, "chat": p1_chat, "action": None,
            "name": p1_data["first_name"],
            "class_id": p1_data["class_id"],
            "hp": p1_data["stats"]["hp"],
            "max_hp": p1_data["stats"]["hp"],
            "stats": p1_data["stats"],
        }
        self.p2 = {
            "id": p2_id, "chat": p2_chat, "action": None,
            "name": p2_data["first_name"],
            "class_id": p2_data["class_id"],
            "hp": p2_data["stats"]["hp"],
            "max_hp": p2_data["stats"]["hp"],
            "stats": p2_data["stats"],
        }

        self.log: list[str] = []
        self.p1_msg_id: int | None = None
        self.p2_msg_id: int | None = None
        self._turn_task: asyncio.Task | None = None

    def get_fighter(self, uid: int) -> dict | None:
        if self.p1["id"] == uid:
            return self.p1
        if self.p2["id"] == uid:
            return self.p2
        return None

    def opponent_of(self, uid: int) -> dict:
        return self.p2 if self.p1["id"] == uid else self.p1

    def both_acted(self) -> bool:
        return (
            self.p1["action"] is not None and
            (self.is_bot or self.p2["action"] is not None)
        )


def battle_keyboard(battle_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚔️ Атака", callback_data=f"battle:attack:{battle_id}"),
            InlineKeyboardButton("✨ Умение", callback_data=f"battle:skill:{battle_id}"),
        ],
        [
            InlineKeyboardButton("🛡️ Защита", callback_data=f"battle:defend:{battle_id}"),
            InlineKeyboardButton("💊 Зелье", callback_data=f"battle:heal:{battle_id}"),
        ],
    ])


def hp_bar(hp: int, max_hp: int, length: int = 8) -> str:
    filled = round(max(hp, 0) / max(max_hp, 1) * length)
    return "█" * filled + "░" * (length - filled)


def battle_status(state: BattleState) -> str:
    p1, p2 = state.p1, state.p2
    return (
        f"⚔️ *РАУНД {state.round}*\n\n"
        f"*{p1['name']}*\n"
        f"❤️ `{hp_bar(p1['hp'], p1['max_hp'])}` {p1['hp']}/{p1['max_hp']}\n\n"
        f"*{p2['name']}*\n"
        f"❤️ `{hp_bar(p2['hp'], p2['max_hp'])}` {p2['hp']}/{p2['max_hp']}\n\n"
        f"Выбери действие:"
    )


# ─── COMBAT MATH ───────────────────────────────────────────────────────────────

def resolve_round(attacker: dict, defender: dict, action_a: str, action_d: str) -> tuple[str, int]:
    """Вычислить урон и эффекты одного столкновения"""
    s_a = attacker["stats"]
    s_d = defender["stats"]
    log = []
    dmg = 0

    # Промах
    hit_roll = random.uniform(0, 100)
    if hit_roll > s_a["accuracy"]:
        log.append(f"💨 *{attacker['name']}* промахнулся!")
        return "\n".join(log), 0

    # Уворот
    if action_d != "defend":
        dodge_roll = random.uniform(0, 100)
        if dodge_roll < s_d["dodge"]:
            log.append(f"⚡️ *{defender['name']}* уклонился!")
            return "\n".join(log), 0

    base_dmg = s_a["atk"]

    # Умение класса
    class_bonus = 1.0
    cls = CLASSES.get(attacker["class_id"], {})
    if action_a == "skill":
        if attacker["class_id"] == "berserker":
            class_bonus = 1.4
            log.append(f"💢 *Ярость!* Атака усилена!")
        elif attacker["class_id"] == "mage":
            s_a["foresight"] = min(99, s_a["foresight"] + 30)
            log.append(f"🧿 *Предчувствие!* Предвидение выросло!")

    # Крит
    crit_roll = random.uniform(0, 100)
    is_crit = crit_roll < s_a["crit_chance"]
    crit_mult = (s_a["crit_power"] / 100) if is_crit else 1.0

    # Ассасин: при крите +50%
    if is_crit and attacker["class_id"] == "assassin" and action_a == "skill":
        crit_mult *= 1.5
        log.append(f"⚡ *Смертельный удар!*")

    # Защита блокирует 40% (или 60% если воин с умением)
    block = 0
    if action_d == "defend":
        if defender["class_id"] == "warrior":
            block_roll = random.uniform(0, 100)
            if block_roll < 25:
                block = 0.60
                log.append(f"🛡️ *{defender['name']}* заблокировал 60% урона!")
            else:
                block = 0.40
        else:
            block = 0.40

    dmg = base_dmg * class_bonus * crit_mult
    dmg = max(1, int(dmg * (1 - block)))

    # Предвидение снижает урон
    foresight_red = s_d["foresight"] / 200  # макс ~25% снижение
    dmg = max(1, int(dmg * (1 - foresight_red)))

    if is_crit and not (attacker["class_id"] == "assassin" and action_a == "skill"):
        log.append(f"💥 *Критический удар!*")

    log.append(f"🗡️ *{attacker['name']}* наносит *{dmg}* урона.")

    # Контрудар
    counter_chance = s_d["counter"]
    if action_d in ("defend", "attack"):
        cnt_roll = random.uniform(0, 100)
        if cnt_roll < counter_chance:
            cnt_dmg = max(1, int(s_d["atk"] * 0.3))
            # Контрудар идёт в attacker.hp — применяется снаружи, вернём как отрицательный offset
            log.append(f"🤺 *{defender['name']}* наносит контрудар: *{cnt_dmg}* урона!")
            dmg = dmg  # основной урон
            return "\n".join(log), (dmg, cnt_dmg)

    return "\n".join(log), (dmg, 0)


# ─── BATTLE HANDLER ────────────────────────────────────────────────────────────

class BattleHandler:

    @staticmethod
    async def start_pvp(app, p1_id: int, p2_id: int, p1_chat: int, p2_chat: int):
        db: Database = app.bot_data["db"]
        p1_data_raw = await db.get_player(p1_id)
        p2_data_raw = await db.get_player(p2_id)
        p1_eq = await db.get_equipped(p1_id)
        p2_eq = await db.get_equipped(p2_id)

        p1_stats, p1_skills = calc_stats(p1_data_raw, p1_eq)
        p2_stats, p2_skills = calc_stats(p2_data_raw, p2_eq)

        p1_data = {**p1_data_raw, "stats": p1_stats}
        p2_data = {**p2_data_raw, "stats": p2_stats}

        battle_id = f"{p1_id}_{p2_id}"
        state = BattleState(
            battle_id, p1_id, p1_chat, p1_data,
            p2_id, p2_chat, p2_data, is_bot=False
        )
        active_battles[battle_id] = state

        intro = (
            f"⚔️ *АРЕНА — БОЙ НАЧИНАЕТСЯ!*\n\n"
            f"*{p1_data['first_name']}* [{CLASSES[p1_data['class_id']]['name']}]\n"
            f"❤️ {p1_stats['hp']} | 🗡 {p1_stats['atk']} | 🔰 {p1_stats['def']}\n\n"
            f"VS\n\n"
            f"*{p2_data['first_name']}* [{CLASSES[p2_data['class_id']]['name']}]\n"
            f"❤️ {p2_stats['hp']} | 🗡 {p2_stats['atk']} | 🔰 {p2_stats['def']}\n\n"
            f"Выбери действие в раунде 1:"
        )

        try:
            msg1 = await app.bot.send_message(
                p1_chat, intro, parse_mode="Markdown",
                reply_markup=battle_keyboard(battle_id)
            )
            msg2 = await app.bot.send_message(
                p2_chat, intro, parse_mode="Markdown",
                reply_markup=battle_keyboard(battle_id)
            )
            state.p1_msg_id = msg1.message_id
            state.p2_msg_id = msg2.message_id
        except Exception as e:
            logger.error(f"PvP send error: {e}")

        # Таймер авто-хода
        state._turn_task = asyncio.create_task(
            BattleHandler._turn_timeout(app, battle_id)
        )

    @staticmethod
    async def start_vs_bot(app, p1_id: int, p1_chat: int):
        db: Database = app.bot_data["db"]
        p1_data_raw = await db.get_player(p1_id)
        if not p1_data_raw:
            return
        p1_eq = await db.get_equipped(p1_id)
        p1_stats, _ = calc_stats(p1_data_raw, p1_eq)
        p1_data = {**p1_data_raw, "stats": p1_stats}

        bot_data = make_bot_opponent(p1_data_raw["level"])
        bot_stats, bot_skills = calc_stats(
            {"level": bot_data["level"], "class_id": bot_data["class_id"]}, {}
        )
        bot_data["stats"] = bot_stats

        battle_id = f"{p1_id}_bot"
        state = BattleState(
            battle_id, p1_id, p1_chat, p1_data,
            0, None, bot_data, is_bot=True
        )
        active_battles[battle_id] = state

        intro = (
            f"⚔️ *АРЕНА — БОЙ С БОТОМ*\n"
            f"_Реальный соперник не найден_\n\n"
            f"*{p1_data['first_name']}* [{CLASSES[p1_data['class_id']]['name']}]\n"
            f"❤️ {p1_stats['hp']} | 🗡 {p1_stats['atk']}\n\n"
            f"VS\n\n"
            f"*{bot_data['first_name']}* [{CLASSES[bot_data['class_id']]['name']}]\n"
            f"❤️ {bot_stats['hp']} | 🗡 {bot_stats['atk']}\n\n"
            f"Выбери действие:"
        )
        try:
            msg = await app.bot.send_message(
                p1_chat, intro, parse_mode="Markdown",
                reply_markup=battle_keyboard(battle_id)
            )
            state.p1_msg_id = msg.message_id
        except Exception as e:
            logger.error(f"Bot battle send error: {e}")

        state._turn_task = asyncio.create_task(
            BattleHandler._turn_timeout(app, battle_id)
        )

    @staticmethod
    async def action(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        uid = query.from_user.id
        parts = query.data.split(":")
        action = parts[1]
        battle_id = parts[2]

        state = active_battles.get(battle_id)
        if not state:
            await query.edit_message_text("⚠️ Бой уже завершён.")
            return

        fighter = state.get_fighter(uid)
        if not fighter:
            await query.answer("Ты не участвуешь в этом бою!", show_alert=True)
            return
        if fighter["action"] is not None:
            await query.answer("Ты уже выбрал действие в этом раунде.", show_alert=True)
            return

        # Зелье — лечение
        if action == "heal":
            heal = int(fighter["max_hp"] * 0.25)
            fighter["hp"] = min(fighter["max_hp"], fighter["hp"] + heal)
            fighter["action"] = "heal"
            await query.edit_message_text(
                f"💊 Ты использовал зелье! +{heal} ОЗ\n\n"
                f"❤️ ОЗ: {fighter['hp']}/{fighter['max_hp']}\n\n"
                f"⏳ Ждём действия противника...",
                parse_mode="Markdown"
            )
        else:
            fighter["action"] = action
            action_names = {
                "attack": "⚔️ Атака", "skill": "✨ Умение", "defend": "🛡️ Защита"
            }
            await query.edit_message_text(
                f"✅ Выбрано: *{action_names.get(action, action)}*\n\n"
                f"⏳ Ждём действия противника...",
                parse_mode="Markdown"
            )

        # Бот ходит сразу
        if state.is_bot and state.p2["action"] is None:
            state.p2["action"] = random.choice(["attack", "attack", "skill", "defend"])

        if state.both_acted():
            if state._turn_task:
                state._turn_task.cancel()
            await BattleHandler._resolve_round(ctx.application, battle_id)

    @staticmethod
    async def _turn_timeout(app, battle_id: str):
        await asyncio.sleep(TURN_TIMEOUT)
        state = active_battles.get(battle_id)
        if not state:
            return
        # Авто-атака для не ответивших
        if state.p1["action"] is None:
            state.p1["action"] = "attack"
        if not state.is_bot and state.p2["action"] is None:
            state.p2["action"] = "attack"
        if state.is_bot and state.p2["action"] is None:
            state.p2["action"] = random.choice(["attack", "skill", "defend"])
        await BattleHandler._resolve_round(app, battle_id)

    @staticmethod
    async def _resolve_round(app, battle_id: str):
        state = active_battles.get(battle_id)
        if not state:
            return

        p1, p2 = state.p1, state.p2
        round_log = [f"*── Раунд {state.round} ──*\n"]

        # p1 атакует p2
        log_text, dmg_result = resolve_round(p1, p2, p1["action"], p2["action"])
        round_log.append(log_text)
        if isinstance(dmg_result, tuple):
            main_dmg, counter_dmg = dmg_result
        else:
            main_dmg, counter_dmg = dmg_result, 0
        p2["hp"] -= main_dmg
        if counter_dmg:
            p1["hp"] -= counter_dmg

        # p2 атакует p1 (если жив)
        if p2["hp"] > 0:
            log_text2, dmg_result2 = resolve_round(p2, p1, p2["action"], p1["action"])
            round_log.append("\n" + log_text2)
            if isinstance(dmg_result2, tuple):
                m2, c2 = dmg_result2
            else:
                m2, c2 = dmg_result2, 0
            p1["hp"] -= m2
            if c2:
                p2["hp"] -= c2

        # Сброс действий
        p1["action"] = None
        p2["action"] = None
        state.round += 1

        # Проверка победителя
        winner_id = None
        if p1["hp"] <= 0 and p2["hp"] <= 0:
            winner_id = -1  # ничья
        elif p1["hp"] <= 0:
            winner_id = p2["id"]
        elif p2["hp"] <= 0:
            winner_id = p1["id"]

        # Боевая сводка раунда
        status = (
            f"\n\n❤️ *{p1['name']}*: {max(0, p1['hp'])}/{p1['max_hp']}\n"
            f"❤️ *{p2['name']}*: {max(0, p2['hp'])}/{p2['max_hp']}"
        )
        round_summary = "\n".join(round_log) + status

        if winner_id is not None:
            await BattleHandler._end_battle(app, battle_id, winner_id, round_summary)
        else:
            # Следующий раунд
            next_text = round_summary + "\n\n*Выбери действие:*"
            try:
                await app.bot.send_message(
                    p1["chat"], next_text, parse_mode="Markdown",
                    reply_markup=battle_keyboard(battle_id)
                )
                if not state.is_bot and p2["chat"]:
                    await app.bot.send_message(
                        p2["chat"], next_text, parse_mode="Markdown",
                        reply_markup=battle_keyboard(battle_id)
                    )
            except Exception as e:
                logger.error(f"Round msg error: {e}")

            state._turn_task = asyncio.create_task(
                BattleHandler._turn_timeout(app, battle_id)
            )

    @staticmethod
    async def _end_battle(app, battle_id: str, winner_id: int, last_log: str):
        state = active_battles.pop(battle_id, None)
        if not state:
            return

        db: Database = app.bot_data["db"]
        p1, p2 = state.p1, state.p2

        is_draw = winner_id == -1

        if is_draw:
            winner_name = "Ничья"
            result_p1 = result_p2 = "🤝 *Ничья!*"
        else:
            winner_name = p1["name"] if winner_id == p1["id"] else p2["name"]
            result_p1 = "🏆 *Ты победил!*" if winner_id == p1["id"] else "💀 *Ты проиграл...*"
            result_p2 = "🏆 *Ты победил!*" if winner_id == p2["id"] else "💀 *Ты проиграл...*"

        # Обновить статы реальных игроков
        if not state.is_bot:
            p1_wins  = 1 if winner_id == p1["id"] else 0
            p1_loss  = 1 if winner_id == p2["id"] else 0
            p2_wins  = 1 if winner_id == p2["id"] else 0
            p2_loss  = 1 if winner_id == p1["id"] else 0

            p1_raw = await db.get_player(p1["id"])
            p2_raw = await db.get_player(p2["id"])

            if p1_raw:
                new_exp1, lvl_msg1 = _add_exp(p1_raw, ARENA_WIN_EXP if p1_wins else ARENA_LOSS_EXP)
                new_gold1 = p1_raw["gold"] + (ARENA_WIN_GOLD if p1_wins else ARENA_LOSS_GOLD)
                await db.update_player(
                    p1["id"],
                    wins=p1_raw["wins"] + p1_wins,
                    losses=p1_raw["losses"] + p1_loss,
                    exp=new_exp1,
                    level=p1_raw["level"] + (1 if lvl_msg1 else 0),
                    gold=new_gold1
                )

            if p2_raw:
                new_exp2, lvl_msg2 = _add_exp(p2_raw, ARENA_WIN_EXP if p2_wins else ARENA_LOSS_EXP)
                new_gold2 = p2_raw["gold"] + (ARENA_WIN_GOLD if p2_wins else ARENA_LOSS_GOLD)
                await db.update_player(
                    p2["id"],
                    wins=p2_raw["wins"] + p2_wins,
                    losses=p2_raw["losses"] + p2_loss,
                    exp=new_exp2,
                    level=p2_raw["level"] + (1 if lvl_msg2 else 0),
                    gold=new_gold2
                )

            await db.save_battle(p1["id"], p2["id"], winner_id if not is_draw else 0, state.round - 1, [])

            end_msg_p1 = (
                f"{last_log}\n\n"
                f"{'━' * 20}\n"
                f"{result_p1}\n"
                f"💰 +{ARENA_WIN_GOLD if p1_wins else ARENA_LOSS_GOLD} золота\n"
                f"✨ +{ARENA_WIN_EXP if p1_wins else ARENA_LOSS_EXP} опыта"
                + (f"\n🎉 *Повышение уровня!*" if (p1_raw and lvl_msg1) else "")
            )
            end_msg_p2 = (
                f"{last_log}\n\n"
                f"{'━' * 20}\n"
                f"{result_p2}\n"
                f"💰 +{ARENA_WIN_GOLD if p2_wins else ARENA_LOSS_GOLD} золота\n"
                f"✨ +{ARENA_WIN_EXP if p2_wins else ARENA_LOSS_EXP} опыта"
                + (f"\n🎉 *Повышение уровня!*" if (p2_raw and lvl_msg2) else "")
            )
        else:
            # PvE (vs бот)
            p1_wins = 1 if winner_id == p1["id"] else 0
            p1_raw = await db.get_player(p1["id"])
            if p1_raw:
                new_exp, lvl_msg = _add_exp(p1_raw, ARENA_WIN_EXP if p1_wins else ARENA_LOSS_EXP)
                new_gold = p1_raw["gold"] + (ARENA_WIN_GOLD if p1_wins else ARENA_LOSS_GOLD)
                await db.update_player(
                    p1["id"],
                    wins=p1_raw["wins"] + p1_wins,
                    losses=p1_raw["losses"] + (1 - p1_wins),
                    exp=new_exp,
                    level=p1_raw["level"] + (1 if lvl_msg else 0),
                    gold=new_gold
                )

            end_msg_p1 = (
                f"{last_log}\n\n"
                f"{'━' * 20}\n"
                f"{result_p1}\n"
                f"💰 +{ARENA_WIN_GOLD if p1_wins else ARENA_LOSS_GOLD} золота\n"
                f"✨ +{ARENA_WIN_EXP if p1_wins else ARENA_LOSS_EXP} опыта"
                + (f"\n🎉 *Повышение уровня!*" if (p1_raw and lvl_msg) else "")
            )
            end_msg_p2 = None

        kb_after = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚔️ Снова в бой", callback_data="arena")],
            [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
        ])

        try:
            await app.bot.send_message(
                p1["chat"], end_msg_p1, parse_mode="Markdown", reply_markup=kb_after
            )
            if end_msg_p2 and p2.get("chat"):
                await app.bot.send_message(
                    p2["chat"], end_msg_p2, parse_mode="Markdown", reply_markup=kb_after
                )
        except Exception as e:
            logger.error(f"End battle msg error: {e}")


def _add_exp(player: dict, exp_gain: int) -> tuple[int, bool]:
    """Добавить опыт, вернуть (новый_exp, leveled_up)"""
    if player["level"] >= MAX_LEVEL:
        return player["exp"], False
    new_exp = player["exp"] + exp_gain
    needed = exp_for_level(player["level"])
    if new_exp >= needed:
        return new_exp - needed, True
    return new_exp, False
