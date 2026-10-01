import asyncio
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

from bot.config.settings import settings
from bot.database.manager import db
from bot.services.logging_service import LoggingService
from bot.services.economy_service import EconomyService
from bot.services.application_service import ApplicationService
from bot.services.ticket_service import TicketService
from bot.services.game_service import GameService

import bot.services.logging_service as logging_module
import bot.services.economy_service as economy_module
import bot.services.application_service as application_module
import bot.services.ticket_service as ticket_module
import bot.services.game_service as game_module


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("viper")


class ViperBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.all()

        super().__init__(
            command_prefix=settings.PREFIX,
            intents=intents,
            case_insensitive=True,
            help_command=None
        )

        self.logging_service = None
        self.economy_service = None
        self.application_service = None
        self.ticket_service = None
        self.game_service = None

    async def setup_hook(self):

        # ========================================
        # DATABASE
        # ========================================

        await db.connect()
        logger.info("Database connected.")

        # ========================================
        # SERVICES
        # ========================================

        self.logging_service = LoggingService(self)
        logging_module.logging_service = self.logging_service

        self.economy_service = EconomyService(
            self.logging_service
        )
        economy_module.economy_service = self.economy_service

        self.application_service = ApplicationService(
            self.logging_service
        )
        application_module.application_service = self.application_service

        self.ticket_service = TicketService(
            self.logging_service
        )
        ticket_module.ticket_service = self.ticket_service

        self.game_service = GameService(
            self.economy_service
        )
        game_module.game_service = self.game_service

        logger.info("Services initialized.")

        # ========================================
        # PREFIX COGS
        # ========================================

        cogs = [
            "bot.cogs.economy",
            "bot.cogs.games",
            "bot.cogs.applications",
            "bot.cogs.admin",
            "bot.cogs.tickets",
            "bot.cogs.fee_calc",
            "bot.cogs.exchange_tickets",
        ]

        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded cog: {cog}")
            except Exception as e:
                logger.exception(
                    f"Failed to load cog {cog}: {e}"
                )

        # ========================================
        # PERSISTENT VIEWS
        # ========================================

        try:
            from bot.views.ticket_views import (
                TicketPanelView,
                TicketCategoryView
            )

            self.add_view(TicketPanelView())
            self.add_view(TicketCategoryView())

            logger.info("Persistent ticket views registered.")

        except Exception as e:
            logger.exception(
                f"Failed to register persistent views: {e}"
            )

        # ========================================
        # PREFIX ONLY
        # ========================================

        logger.info("Prefix command mode enabled.")

    async def on_ready(self):

        logger.info(
            f"Viper Bot is online as {self.user}"
        )

        logger.info(
            f"Connected to {len(self.guilds)} server(s)."
        )

        logger.info(
            f"Prefix: {settings.PREFIX}"
        )

        await self.change_presence(
            activity=discord.Game(
                name=f"Viper | {settings.PREFIX}help"
            )
        )


async def main():

    load_dotenv()

    bot = ViperBot()

    async with bot:
        await bot.start(settings.TOKEN)


if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        logger.info("Bot stopped.")

    except Exception as e:
        logger.exception(
            f"Fatal bot error: {type(e).__name__}: {e}"
        )
