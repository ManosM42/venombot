
import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()


def get_env_int(name: str, default: int = 0) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_channel_id = get_env_int("LOG_CHANNEL_ID")

    async def send_log(self, message: str):
        """Send a message to the configured log channel."""

        if not self.log_channel_id:
            return

        channel = self.bot.get_channel(self.log_channel_id)

        if channel is None:
            return

        try:
            await channel.send(f"📝 **Log:** {message}")
        except discord.HTTPException:
            pass

    @commands.command(name="say")
    @commands.has_permissions(administrator=True)
    async def say(self, ctx, *, text: str):
        """Makes the bot repeat a message."""

        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

        try:
            await ctx.send(text)
        except discord.Forbidden:
            await ctx.send(
                "❌ I don't have permission to send messages here."
            )

    @commands.command(name="dmall")
    @commands.has_permissions(administrator=True)
    async def dm_all(self, ctx, *, message: str):
        """
        Sends a DM to all non-bot members.
        Requires confirmation to prevent accidental execution.
        """

        members = [
            member
            for member in ctx.guild.members
            if not member.bot
        ]

        if not members:
            await ctx.send("❌ There are no eligible members to DM.")
            return

        embed = discord.Embed(
            title="⚠️ Confirm Mass DM",
            description=(
                f"This will attempt to DM **{len(members)} members**.\n\n"
                f"Message:\n> {message[:1000]}\n\n"
                "This operation may take a while and some users may "
                "have DMs disabled."
            ),
            color=discord.Color.orange()
        )

        confirmation_message = await ctx.send(embed=embed)

        await confirmation_message.add_reaction("✅")
        await confirmation_message.add_reaction("❌")

        def check(reaction, user):
            return (
                user == ctx.author
                and reaction.message.id == confirmation_message.id
                and str(reaction.emoji) in ("✅", "❌")
            )

        try:
            reaction, _ = await self.bot.wait_for(
                "reaction_add",
                timeout=30,
                check=check
            )
        except asyncio.TimeoutError:
            await confirmation_message.edit(
                content="⌛ Mass DM cancelled because confirmation timed out.",
                embed=None
            )
            return

        if str(reaction.emoji) == "❌":
            await confirmation_message.edit(
                content="❌ Mass DM cancelled.",
                embed=None
            )
            return

        await confirmation_message.edit(
            content="📨 Starting mass DM...",
            embed=None
        )

        count = 0
        failed = 0

        for member in members:
            try:
                await member.send(message)
                count += 1

                # Small delay to reduce rate-limit pressure.
                await asyncio.sleep(0.5)

            except (
                discord.Forbidden,
                discord.HTTPException,
                discord.NotFound
            ):
                failed += 1

            except Exception:
                failed += 1

        await ctx.send(
            f"✅ **Mass DM finished.**\n"
            f"Successful: `{count}`\n"
            f"Failed: `{failed}`"
        )

        await self.send_log(
            f"{ctx.author} used `!dmall`. "
            f"Successful: {count}, Failed: {failed}"
        )

    @say.error
    async def say_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                "❌ You need Administrator permission to use `!say`."
            )

    @dm_all.error
    async def dm_all_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                "❌ You need Administrator permission to use `!dmall`."
            )


async def setup(bot):
    await bot.add_cog(Admin(bot))

