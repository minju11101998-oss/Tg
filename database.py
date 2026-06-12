"""Слой базы данных — SQLite через aiosqlite"""

import aiosqlite
import json
from config import DB_PATH


class Database:
    def __init__(self):
        self.path = DB_PATH
        self._db: aiosqlite.Connection | None = None

    async def init(self):
        self._db = await aiosqlite.connect(self.path)
        self._db.row_factory = aiosqlite.Row
        await self._create_tables()

    async def _create_tables(self):
        await self._db.executescript("""
        CREATE TABLE IF NOT EXISTS players (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            first_name  TEXT,
            class_id    TEXT DEFAULT 'warrior',
            level       INTEGER DEFAULT 1,
            exp         INTEGER DEFAULT 0,
            gold        INTEGER DEFAULT 100,
            wins        INTEGER DEFAULT 0,
            losses      INTEGER DEFAULT 0,
            is_banned   INTEGER DEFAULT 0,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS equipment_slots (
            user_id     INTEGER,
            slot        TEXT,
            item_id     TEXT,
            PRIMARY KEY (user_id, slot),
            FOREIGN KEY (user_id) REFERENCES players(user_id)
        );

        CREATE TABLE IF NOT EXISTS inventory (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            item_id     TEXT,
            FOREIGN KEY (user_id) REFERENCES players(user_id)
        );

        CREATE TABLE IF NOT EXISTS battles (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            player1_id      INTEGER,
            player2_id      INTEGER,
            winner_id       INTEGER,
            rounds          INTEGER,
            log             TEXT,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)
        await self._db.commit()

    # ── Player ──────────────────────────────────────────────────────────────

    async def get_player(self, user_id: int) -> dict | None:
        async with self._db.execute(
            "SELECT * FROM players WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    async def create_player(self, user_id: int, username: str, first_name: str, class_id: str):
        await self._db.execute(
            """INSERT OR IGNORE INTO players 
               (user_id, username, first_name, class_id, gold)
               VALUES (?, ?, ?, ?, 200)""",
            (user_id, username, first_name, class_id)
        )
        await self._db.commit()

    async def update_player(self, user_id: int, **kwargs):
        if not kwargs:
            return
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [user_id]
        await self._db.execute(f"UPDATE players SET {sets} WHERE user_id = ?", vals)
        await self._db.commit()

    async def get_leaderboard(self, limit: int = 10) -> list[dict]:
        async with self._db.execute(
            """SELECT user_id, username, first_name, level, wins, losses
               FROM players ORDER BY wins DESC, level DESC LIMIT ?""",
            (limit,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def get_all_players(self) -> list[dict]:
        async with self._db.execute("SELECT * FROM players WHERE is_banned = 0") as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def count_players(self) -> int:
        async with self._db.execute("SELECT COUNT(*) FROM players") as cur:
            return (await cur.fetchone())[0]

    async def count_battles(self) -> int:
        async with self._db.execute("SELECT COUNT(*) FROM battles") as cur:
            return (await cur.fetchone())[0]

    # ── Equipment ────────────────────────────────────────────────────────────

    async def get_equipped(self, user_id: int) -> dict[str, str]:
        async with self._db.execute(
            "SELECT slot, item_id FROM equipment_slots WHERE user_id = ?", (user_id,)
        ) as cur:
            return {row["slot"]: row["item_id"] for row in await cur.fetchall()}

    async def equip_item(self, user_id: int, slot: str, item_id: str):
        await self._db.execute(
            """INSERT INTO equipment_slots (user_id, slot, item_id)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id, slot) DO UPDATE SET item_id = excluded.item_id""",
            (user_id, slot, item_id)
        )
        await self._db.commit()

    async def unequip_item(self, user_id: int, slot: str):
        await self._db.execute(
            "DELETE FROM equipment_slots WHERE user_id = ? AND slot = ?",
            (user_id, slot)
        )
        await self._db.commit()

    async def add_to_inventory(self, user_id: int, item_id: str):
        await self._db.execute(
            "INSERT INTO inventory (user_id, item_id) VALUES (?, ?)",
            (user_id, item_id)
        )
        await self._db.commit()

    async def get_inventory(self, user_id: int) -> list[str]:
        async with self._db.execute(
            "SELECT item_id FROM inventory WHERE user_id = ?", (user_id,)
        ) as cur:
            return [row["item_id"] for row in await cur.fetchall()]

    async def has_item(self, user_id: int, item_id: str) -> bool:
        async with self._db.execute(
            "SELECT 1 FROM inventory WHERE user_id = ? AND item_id = ? LIMIT 1",
            (user_id, item_id)
        ) as cur:
            return bool(await cur.fetchone())

    # ── Battles ──────────────────────────────────────────────────────────────

    async def save_battle(self, p1: int, p2: int, winner: int, rounds: int, log: list):
        await self._db.execute(
            """INSERT INTO battles (player1_id, player2_id, winner_id, rounds, log)
               VALUES (?, ?, ?, ?, ?)""",
            (p1, p2, winner, rounds, json.dumps(log, ensure_ascii=False))
        )
        await self._db.commit()
