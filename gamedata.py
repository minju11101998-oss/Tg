"""Игровые данные: классы, экипировка, формулы статов"""

# ─── КЛАССЫ ────────────────────────────────────────────────────────────────────
# Базовые навыки героя (растут с уровнем)
# Сила → Атака, Выносливость → HP/Защита, Ловкость → Уворот/Крит, Интуиция → Предвидение/Контрудар

CLASSES = {
    "warrior": {
        "name": "⚔️ Воин",
        "desc": "Мастер ближнего боя. Высокая защита и HP. Сила — первична.",
        "emoji": "⚔️",
        # Базовые навыки
        "strength": 8,       # ✊ Сила
        "endurance": 7,      # ♥️ Выносливость
        "agility": 4,        # 💫 Ловкость
        "intuition": 3,      # 🧿 Интуиция
        # Бонусы роста за уровень
        "str_growth": 2.0,
        "end_growth": 1.8,
        "agi_growth": 0.8,
        "int_growth": 0.6,
        "skill": "🛡️ Блок",
        "skill_desc": "25% шанс заблокировать 60% урона",
    },
    "assassin": {
        "name": "🗡️ Ассасин",
        "desc": "Скоростной убийца. Высокий крит и уворот. Ловкость — первична.",
        "emoji": "🗡️",
        "strength": 6,
        "endurance": 4,
        "agility": 9,
        "intuition": 5,
        "str_growth": 1.5,
        "end_growth": 0.8,
        "agi_growth": 2.2,
        "int_growth": 1.2,
        "skill": "⚡ Смертельный удар",
        "skill_desc": "При крите наносит +50% урона",
    },
    "mage": {
        "name": "🔮 Маг",
        "desc": "Контролирует бой через предвидение. Интуиция — первична.",
        "emoji": "🔮",
        "strength": 5,
        "endurance": 4,
        "agility": 5,
        "intuition": 10,
        "str_growth": 1.2,
        "end_growth": 0.9,
        "agi_growth": 1.0,
        "int_growth": 2.5,
        "skill": "🧿 Предчувствие",
        "skill_desc": "+30% к предвидению и контрудару",
    },
    "berserker": {
        "name": "💢 Берсерк",
        "desc": "Безудержная ярость. Огромная атака, низкая защита.",
        "emoji": "💢",
        "strength": 11,
        "endurance": 5,
        "agility": 5,
        "intuition": 2,
        "str_growth": 2.8,
        "end_growth": 0.9,
        "agi_growth": 1.1,
        "int_growth": 0.4,
        "skill": "💥 Ярость",
        "skill_desc": "Атака +40%, но защита -20% в этом ходу",
    },
}

# ─── ФОРМУЛЫ СТАТОВ ────────────────────────────────────────────────────────────

def calc_skills(player: dict, cls: dict) -> dict:
    """Вычислить навыки героя с учётом уровня"""
    lvl = player["level"]
    return {
        "strength":   cls["strength"]   + int(cls["str_growth"] * (lvl - 1)),
        "endurance":  cls["endurance"]  + int(cls["end_growth"]  * (lvl - 1)),
        "agility":    cls["agility"]    + int(cls["agi_growth"]  * (lvl - 1)),
        "intuition":  cls["intuition"]  + int(cls["int_growth"]  * (lvl - 1)),
    }

def calc_stats(player: dict, equipped: dict[str, str]) -> dict:
    """Вычислить боевые статы игрока из навыков + экипировки"""
    cls = CLASSES[player["class_id"]]
    skills = calc_skills(player, cls)
    
    s = skills["strength"]
    e = skills["endurance"]
    a = skills["agility"]
    i = skills["intuition"]

    # Базовые боевые статы из навыков
    stats = {
        "hp":           80 + e * 12,                # ❤️ Здоровье
        "atk":          10 + s * 3,                  # 🗡 Атака
        "def":          5  + e * 2,                  # 🔰 Защита
        "crit_chance":  3  + a * 1.2,                # 🥊 Крит (%)
        "crit_power":   140 + s * 2,                 # 💥 Сила крита (%)
        "foresight":    2  + i * 1.5,                # 👁 Предвидение (% уклон от крита)
        "dodge":        2  + a * 1.3,                # ⚡️ Уворот (%)
        "counter":      1  + i * 0.8,                # 🤺 Контрудар (% урон назад)
        "accuracy":     85 + a * 0.5,                # 🎯 Точность (%)
    }

    # Бонусы экипировки
    for slot, item_id in equipped.items():
        if item_id and item_id in ITEMS:
            item = ITEMS[item_id]
            for stat, val in item.get("stats", {}).items():
                if stat in stats:
                    stats[stat] += val

    # Округление
    for k in ["crit_chance", "foresight", "dodge", "counter", "accuracy"]:
        stats[k] = round(stats[k], 1)
    for k in ["hp", "atk", "def", "crit_power"]:
        stats[k] = int(stats[k])

    return stats, skills

def stats_text(stats: dict, skills: dict) -> str:
    return (
        f"❤️ Здоровье: *{stats['hp']}*\n"
        f"🗡 Атака: *{stats['atk']}*\n"
        f"🔰 Защита: *{stats['def']}*\n"
        f"🥊 Крит: *{stats['crit_chance']}%*\n"
        f"💥 Сила крита: *{stats['crit_power']}%*\n"
        f"👁 Предвидение: *{stats['foresight']}%*\n"
        f"⚡️ Уворот: *{stats['dodge']}%*\n"
        f"🤺 Контрудар: *{stats['counter']}%*\n"
        f"🎯 Точность: *{stats['accuracy']}%*\n"
        f"\n*Навыки героя:*\n"
        f"✊ Сила: *{skills['strength']}*\n"
        f"♥️ Выносливость: *{skills['endurance']}*\n"
        f"💫 Ловкость: *{skills['agility']}*\n"
        f"🧿 Интуиция: *{skills['intuition']}*"
    )

# ─── ЭКИПИРОВКА ────────────────────────────────────────────────────────────────
# Слоты: weapon, armor, helmet, boots, ring, amulet

SLOTS = {
    "weapon":  "🗡️ Оружие",
    "armor":   "🛡️ Броня",
    "helmet":  "⛑️ Шлем",
    "boots":   "👢 Сапоги",
    "ring":    "💍 Кольцо",
    "amulet":  "📿 Амулет",
}

# Ключ → предмет
# req_level: минимальный уровень для покупки/экипировки
# price: стоимость в золоте
ITEMS = {
    # ══ ОРУЖИЕ ══
    "iron_sword": {
        "name": "⚔️ Железный меч",
        "slot": "weapon",
        "desc": "Простое, но надёжное оружие.",
        "req_level": 1,
        "price": 80,
        "stats": {"atk": 8, "accuracy": 2},
    },
    "steel_sword": {
        "name": "⚔️ Стальной меч",
        "slot": "weapon",
        "desc": "Сбалансированное оружие опытного воина.",
        "req_level": 5,
        "price": 200,
        "stats": {"atk": 18, "crit_chance": 3, "accuracy": 3},
    },
    "shadow_blade": {
        "name": "🗡️ Клинок тени",
        "slot": "weapon",
        "desc": "Кованный во тьме — смертоносен в руках ассасина.",
        "req_level": 10,
        "price": 450,
        "stats": {"atk": 28, "crit_chance": 8, "crit_power": 25, "dodge": 3},
    },
    "war_axe": {
        "name": "🪓 Боевой топор",
        "slot": "weapon",
        "desc": "Тяжёлый. Медленный. Убивает наверняка.",
        "req_level": 8,
        "price": 320,
        "stats": {"atk": 35, "crit_power": 30, "accuracy": -5},
    },
    "arcane_staff": {
        "name": "🪄 Магический посох",
        "slot": "weapon",
        "desc": "Усиливает интуицию и предвидение.",
        "req_level": 7,
        "price": 380,
        "stats": {"atk": 20, "foresight": 8, "counter": 5},
    },
    "dragon_sword": {
        "name": "🔥 Меч дракона",
        "slot": "weapon",
        "desc": "Легендарное оружие. Горит пламенем.",
        "req_level": 20,
        "price": 1200,
        "stats": {"atk": 55, "crit_chance": 12, "crit_power": 40, "accuracy": 5},
    },

    # ══ БРОНЯ ══
    "leather_armor": {
        "name": "🧥 Кожаная броня",
        "slot": "armor",
        "desc": "Лёгкая, не стесняет движений.",
        "req_level": 1,
        "price": 70,
        "stats": {"def": 5, "dodge": 2, "hp": 20},
    },
    "chain_mail": {
        "name": "⛓️ Кольчуга",
        "slot": "armor",
        "desc": "Хороший баланс защиты и мобильности.",
        "req_level": 5,
        "price": 180,
        "stats": {"def": 12, "hp": 50},
    },
    "plate_armor": {
        "name": "🛡️ Латные доспехи",
        "slot": "armor",
        "desc": "Тяжёлая, но непробиваемая защита.",
        "req_level": 10,
        "price": 420,
        "stats": {"def": 25, "hp": 100, "dodge": -3},
    },
    "shadow_cloak": {
        "name": "🌑 Плащ теней",
        "slot": "armor",
        "desc": "Сливается с темнотой. Трудно попасть.",
        "req_level": 12,
        "price": 500,
        "stats": {"def": 10, "dodge": 12, "hp": 40},
    },
    "dragon_scale": {
        "name": "🐉 Чешуя дракона",
        "slot": "armor",
        "desc": "Практически непробиваема. Легендарная.",
        "req_level": 20,
        "price": 1400,
        "stats": {"def": 45, "hp": 180, "counter": 8},
    },

    # ══ ШЛЕМ ══
    "leather_helm": {
        "name": "⛑️ Кожаный шлем",
        "slot": "helmet",
        "desc": "Защищает голову.",
        "req_level": 1,
        "price": 50,
        "stats": {"def": 3, "hp": 15},
    },
    "iron_helm": {
        "name": "🪖 Железный шлем",
        "slot": "helmet",
        "desc": "Защита и немного интуиции.",
        "req_level": 5,
        "price": 140,
        "stats": {"def": 8, "hp": 30, "foresight": 2},
    },
    "war_crown": {
        "name": "👑 Боевая корона",
        "slot": "helmet",
        "desc": "Символ власти и мощи.",
        "req_level": 15,
        "price": 700,
        "stats": {"def": 15, "hp": 60, "atk": 10, "foresight": 5},
    },

    # ══ САПОГИ ══
    "light_boots": {
        "name": "👟 Лёгкие сапоги",
        "slot": "boots",
        "desc": "Быстро, тихо, точно.",
        "req_level": 1,
        "price": 60,
        "stats": {"dodge": 4, "accuracy": 3},
    },
    "iron_boots": {
        "name": "🥾 Железные сапоги",
        "slot": "boots",
        "desc": "Тяжёлые, но защита ног не знает равных.",
        "req_level": 6,
        "price": 160,
        "stats": {"def": 7, "hp": 25, "dodge": -1},
    },
    "phantom_boots": {
        "name": "💨 Сапоги призрака",
        "slot": "boots",
        "desc": "Кажется, ты не касаешься земли.",
        "req_level": 14,
        "price": 600,
        "stats": {"dodge": 15, "accuracy": 8, "counter": 3},
    },

    # ══ КОЛЬЦО ══
    "iron_ring": {
        "name": "💍 Железное кольцо",
        "slot": "ring",
        "desc": "Небольшой бонус к атаке.",
        "req_level": 3,
        "price": 90,
        "stats": {"atk": 5},
    },
    "berserker_ring": {
        "name": "🔴 Кольцо берсерка",
        "slot": "ring",
        "desc": "Сила крита зашкаливает.",
        "req_level": 8,
        "price": 250,
        "stats": {"crit_chance": 6, "crit_power": 20, "def": -3},
    },
    "oracle_ring": {
        "name": "🔵 Кольцо оракула",
        "slot": "ring",
        "desc": "Видит то, что скрыто.",
        "req_level": 10,
        "price": 300,
        "stats": {"foresight": 10, "counter": 6, "intuition": 0},
    },

    # ══ АМУЛЕТ ══
    "life_amulet": {
        "name": "❤️ Амулет жизни",
        "slot": "amulet",
        "desc": "Увеличивает запас здоровья.",
        "req_level": 4,
        "price": 120,
        "stats": {"hp": 60},
    },
    "war_amulet": {
        "name": "⚔️ Амулет войны",
        "slot": "amulet",
        "desc": "Всё ради победы.",
        "req_level": 9,
        "price": 280,
        "stats": {"atk": 12, "crit_chance": 4},
    },
    "shadow_amulet": {
        "name": "🌑 Амулет теней",
        "slot": "amulet",
        "desc": "Ты — тень. Тебя нет.",
        "req_level": 15,
        "price": 650,
        "stats": {"dodge": 10, "counter": 8, "foresight": 6},
    },
}

# Группировка по слотам для магазина
def items_by_slot(slot: str, min_level: int = 1) -> list[tuple[str, dict]]:
    return [
        (iid, item) for iid, item in ITEMS.items()
        if item["slot"] == slot and item["req_level"] <= min_level
    ]

def items_by_slot_all(slot: str) -> list[tuple[str, dict]]:
    return [(iid, item) for iid, item in ITEMS.items() if item["slot"] == slot]
