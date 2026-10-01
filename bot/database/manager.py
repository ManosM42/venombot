import aiosqlite
import logging
from bot.config.settings import settings

DB_PATH = "viper_database.db"
logger = logging.getLogger("viper.database")

class DatabaseManager:
    def __init__(self):
        self.db = None

    async def connect(self):
        self.db = await aiosqlite.connect(DB_PATH)
        self.db.row_factory = aiosqlite.Row
        await self.init_db()

    async def disconnect(self):
        if self.db:
            await self.db.close()

    async def init_db(self):
        """Initializes all tables for the bot."""
        # Users economy table (Guild scoped)
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                guild_id INTEGER,
                user_id INTEGER,
                balance INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            )
        """)

        # Economy Transactions
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                amount INTEGER,
                type TEXT,
                game_session_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Applications
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                app_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                content TEXT,
                status TEXT DEFAULT 'pending',
                reviewer_id INTEGER,
                reviewed_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tickets
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id TEXT PRIMARY KEY,
                guild_id INTEGER,
                user_id INTEGER,
                channel_id INTEGER,
                category TEXT,
                status TEXT DEFAULT 'open',
                claimer_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                closed_at DATETIME,
                close_reason TEXT
            )
        """)

        await self.db.commit()

    async def execute(self, query, params=()):
        async with self.db.execute(query, params) as cursor:
            await self.db.commit()
            return cursor.lastrowid

    async def fetchone(self, query, params=()):
        async with self.db.execute(query, params) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, query, params=()):
        async with self.db.execute(query, params) as cursor:
            return await cursor.fetchall()

db = DatabaseManager()
