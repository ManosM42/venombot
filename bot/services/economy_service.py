import logging

from bot.database.manager import db
from bot.config.settings import settings

logger = logging.getLogger("viper.economy")


class EconomyService:

    def __init__(self, logging_service=None):
        self.logging_service = logging_service

    async def _ensure_user(self, guild_id: int, user_id: int):
        await db.execute(
            "INSERT OR IGNORE INTO users (guild_id, user_id, balance) VALUES (?, ?, ?)",
            (guild_id, user_id, settings.STARTING_BALANCE),
        )

    async def get_balance(self, guild_id: int, user_id: int) -> int:
        await self._ensure_user(guild_id, user_id)
        row = await db.fetchone(
            "SELECT balance FROM users WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        return row["balance"] if row else 0

    async def add_coins(
        self,
        guild_id: int,
        user_id: int,
        amount: int,
        reason: str = "",
        session_id: str | None = None,
    ):
        await self._ensure_user(guild_id, user_id)

        await db.execute(
            "UPDATE users SET balance = balance + ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE guild_id = ? AND user_id = ?",
            (amount, guild_id, user_id),
        )

        await db.execute(
            "INSERT INTO transactions (guild_id, user_id, amount, type, game_session_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (guild_id, user_id, amount, reason, session_id),
        )

        if self.logging_service:
            try:
                import discord
                await self.logging_service.log(
                    category="Economy",
                    message=f"<@{user_id}> received **{amount:,} coins** ({reason})",
                    color=discord.Color.green(),
                )
            except Exception as e:
                logger.warning(f"Logging failed in add_coins: {e}")

    async def spend_coins(
        self,
        guild_id: int,
        user_id: int,
        amount: int,
        reason: str = "",
        session_id: str | None = None,
    ) -> bool:
        await self._ensure_user(guild_id, user_id)

        row = await db.fetchone(
            "SELECT balance FROM users WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        balance = row["balance"] if row else 0

        if balance < amount:
            return False

        await db.execute(
            "UPDATE users SET balance = balance - ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE guild_id = ? AND user_id = ?",
            (amount, guild_id, user_id),
        )

        await db.execute(
            "INSERT INTO transactions (guild_id, user_id, amount, type, game_session_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (guild_id, user_id, -amount, reason, session_id),
        )

        return True

    async def get_leaderboard(self, guild_id: int, limit: int = 10):
        rows = await db.fetchall(
            "SELECT user_id, balance FROM users WHERE guild_id = ? "
            "ORDER BY balance DESC LIMIT ?",
            (guild_id, limit),
        )
        return [{"user_id": r["user_id"], "balance": r["balance"]} for r in rows]