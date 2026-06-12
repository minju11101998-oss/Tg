"""Конфигурация бота"""

BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # ← вставь токен

# Telegram user_id администраторов
ADMIN_IDS = [123456789]  # ← вставь свой user_id

# Время ожидания противника (секунды) перед матчем с ботом
MATCHMAKING_TIMEOUT = 30

# База данных
DB_PATH = "arena.db"

# Экономика
ARENA_WIN_GOLD = 50
ARENA_LOSS_GOLD = 10
ARENA_WIN_EXP = 80
ARENA_LOSS_EXP = 20

# Опыт для повышения уровня: exp_needed = BASE * level^SCALE
EXP_BASE = 100
EXP_SCALE = 1.5

# Макс. уровень
MAX_LEVEL = 50

# Ход длится N секунд прежде чем автоматически выбирается "атака"
TURN_TIMEOUT = 45
