import aiosqlite
import os

DB_PATH = "bot_database.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # User economy table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0
            )
        """)
        # Applications table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                app_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                content TEXT,
                status TEXT DEFAULT 'pending'
            )
        """)
        await db.commit()

async def get_balance(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
            return 0

async def update_balance(user_id, amount):
    async with aiosqlite.connect(DB_PATH) as db:
        # Check if user exists
        async with db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)) as cursor:
            exists = await cursor.fetchone()

        if exists:
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        else:
            await db.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, amount))
        await db.commit()

async def save_application(user_id, content):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("INSERT INTO applications (user_id, content) VALUES (?, ?)", (user_id, content))
        await db.commit()
        return cursor.lastrowid

async def update_application_status(app_id, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE applications SET status = ? WHERE app_id = ?", (status, app_id))
        await db.commit()
