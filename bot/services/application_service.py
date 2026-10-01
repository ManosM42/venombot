import discord
from bot.database.manager import db
from bot.config.settings import settings
import uuid

class ApplicationService:
    def __init__(self, logging_service):
        self.logging_service = logging_service

    async def submit_application(self, guild_id: int, user_id: int, content: str):
        # Prevent duplicate active applications
        existing = await db.fetchone(
            "SELECT app_id FROM applications WHERE guild_id = ? AND user_id = ? AND status = 'pending'",
            (guild_id, user_id)
        )
        if existing:
            return None, "You already have a pending application."

        app_id = await db.execute(
            "INSERT INTO applications (guild_id, user_id, content) VALUES (?, ?, ?)",
            (guild_id, user_id, content)
        )

        return app_id, None

    async def update_status(self, app_id: int, status: str, reviewer_id: int):
        await db.execute(
            "UPDATE applications SET status = ?, reviewer_id = ?, reviewed_at = CURRENT_TIMESTAMP WHERE app_id = ?",
            (status, reviewer_id, app_id)
        )
        return True

    async def get_application(self, app_id: int):
        return await db.fetchone("SELECT * FROM applications WHERE app_id = ?", (app_id,))

application_service = None # To be initialized in main.py
