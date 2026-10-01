import discord
import uuid
import datetime
from bot.database.manager import db
from bot.config.settings import settings

class TicketService:
    def __init__(self, logging_service):
        self.logging_service = logging_service

    async def create_ticket(self, guild: discord.Guild, user: discord.Member, category_name: str, issue: str):
        ticket_id = str(uuid.uuid4())[:8]
        category_id = settings.TICKET_CATEGORY_ID
        category = guild.get_channel(category_id) if category_id != 0 else None

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        staff_role_id = settings.STAFF_ROLE_ID
        if staff_role_id != 0:
            staff_role = guild.get_role(staff_role_id)
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=f"ticket-{ticket_id}",
            category=category,
            overwrites=overwrites
        )

        await db.execute(
            "INSERT INTO tickets (ticket_id, guild_id, user_id, channel_id, category, status) VALUES (?, ?, ?, ?, ?, ?)",
            (ticket_id, guild.id, user.id, channel.id, category_name, "open")
        )

        return channel, ticket_id

    async def claim_ticket(self, ticket_id: str, staff_id: int):
        await db.execute(
            "UPDATE tickets SET claimer_id = ? WHERE ticket_id = ?",
            (staff_id, ticket_id)
        )

    async def close_ticket(self, ticket_id: str, reason: str = None):
        await db.execute(
            "UPDATE tickets SET status = 'closed', closed_at = CURRENT_TIMESTAMP, close_reason = ? WHERE ticket_id = ?",
            (reason, ticket_id)
        )

    async def get_ticket(self, ticket_id: str):
        return await db.fetchone("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,))

    async def get_ticket_by_channel(self, channel_id: int):
        return await db.fetchone("SELECT * FROM tickets WHERE channel_id = ?", (channel_id,))

ticket_service = None # To be initialized in main.py
