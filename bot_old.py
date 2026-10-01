
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

import database


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = os.getenv("PREFIX", "!").strip() or "!"


# ============================================================
# INTENTS
# ============================================================

intents = discord.Intents.default()

# Required for prefix commands such as !say, !apply, etc.
intents.message_content = True

# Required for member-related features such as !dmall
intents.members = True

# Presence intent
intents.presences = True


# ============================================================
# BOT
# ============================================================

class MyBot(commands.Bot):

    def __init__(self):
        super().__init__(
            command_prefix=PREFIX,
            intents=intents,
            case_insensitive=True,
            help_command=None
        )

    # --------------------------------------------------------
    # STARTUP
    # --------------------------------------------------------

    async def setup_hook(self):

        print("========================================")
        print("Starting bot setup...")
        print("========================================")

        # Initialize database
        try:
            await database.init_db()
            print("✓ Database initialized")
        except Exception as e:
            print(f"✗ Database initialization failed: {type(e).__name__}: {e}")

        # Load cogs
        cogs_folder = "./cogs"

        if not os.path.exists(cogs_folder):
            print("✗ ERROR: ./cogs folder does not exist!")
            return

        for filename in sorted(os.listdir(cogs_folder)):

            if not filename.endswith(".py"):
                continue

            if filename.startswith("_"):
                continue

            extension = f"cogs.{filename[:-3]}"

            try:
                await self.load_extension(extension)
                print(f"✓ Loaded extension: {filename}")

            except Exception as e:
                print(f"✗ Failed to load extension: {filename}")
                print(f"  Error: {type(e).__name__}: {e}")

        # Show loaded commands
        print("----------------------------------------")
        print("Loaded prefix commands:")

        if self.commands:
            for command in sorted(self.commands, key=lambda c: c.name):
                print(f"  !{command.name}")
        else:
            print("  !!! NO PREFIX COMMANDS LOADED !!!")

        print("----------------------------------------")


    # --------------------------------------------------------
    # READY
    # --------------------------------------------------------

    async def on_ready(self):

        print("========================================")
        print(f"✓ Logged in as: {self.user}")
        print(f"✓ Bot ID: {self.user.id}")
        print(f"✓ Prefix: {PREFIX}")
        print(f"✓ Servers: {len(self.guilds)}")
        print("========================================")

        print("Bot is ready.")


    # --------------------------------------------------------
    # MESSAGE HANDLER
    # --------------------------------------------------------
    #
    # IMPORTANT:
    # If you override on_message, you MUST call
    # process_commands().
    #
    # This guarantees that !commands are processed.
    # --------------------------------------------------------

    async def on_message(self, message: discord.Message):

        # Ignore messages sent by bots
        if message.author.bot:
            return

        # Debug information in terminal
        print(
            f"[MESSAGE] "
            f"{message.guild.name if message.guild else 'DM'} | "
            f"{message.author} | "
            f"{message.content}"
        )

        # Process prefix commands
        await self.process_commands(message)


# ============================================================
# CREATE BOT
# ============================================================

bot = MyBot()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    if not TOKEN:
        print("========================================")
        print("✗ ERROR")
        print("DISCORD_TOKEN is missing from .env")
        print("========================================")

    else:

        try:
            bot.run(TOKEN)

        except discord.LoginFailure:
            print("========================================")
            print("✗ ERROR: Discord rejected the bot token.")
            print("Generate/reset the token in Discord Developer Portal.")
            print("========================================")

        except discord.PrivilegedIntentsRequired:
            print("========================================")
            print("✗ ERROR: Privileged Gateway Intents are required.")
            print("")
            print("Enable these in Discord Developer Portal:")
            print("  ✓ Presence Intent")
            print("  ✓ Server Members Intent")
            print("  ✓ Message Content Intent")
            print("========================================")

        except Exception as e:
            print("========================================")
            print(f"✗ ERROR: {type(e).__name__}: {e}")
            print("========================================")

