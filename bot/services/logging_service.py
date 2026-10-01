import discord
from bot.config.settings import settings
import logging

logger = logging.getLogger("viper.logging")

class LoggingService:
    def __init__(self, bot):
        self.bot = bot
        self.log_channel_id = settings.LOG_CHANNEL_ID

    async def log(self, category: str, message: str, user=None, guild=None, color=discord.Color.blue(), extra_info=None):
        """
        Centralized logging method.
        categories: Moderation, Tickets, Applications, Economy, Games, Admin, Errors, Security
        """
        if self.log_channel_id == 0:
            return

        channel = self.bot.get_channel(self.log_channel_id)
        if not channel:
            logger.error(f"Could not find log channel with ID {self.log_channel_id}")
            return

        embed = discord.Embed(
            title=f"🔔 {category} Log",
            description=message,
            color=color,
            timestamp=discord.utils.utcnow()
        )

        if user:
            embed.set_author(name=f"{user} (ID: {user.id})")

        if guild:
            embed.add_field(name="Guild", value=guild.name, inline=True)

        if extra_info:
            for key, value in extra_info.items():
                embed.add_field(name=key, value=value, inline=True)

        await channel.send(embed=embed)

    async def log_error(self, error, context=None):
        """Logs an error to the log channel and the system logger."""
        logger.exception(f"Error occurred: {error}")
        await self.log(
            category="Errors",
            message=f"An unexpected error occurred: {str(error)}",
            color=discord.Color.red(),
            extra_info={"Context": str(context)}
        )

logging_service = None # To be initialized in main.py
