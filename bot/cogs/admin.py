import discord
from discord import app_commands
from discord.ext import commands
import os
from bot.config.settings import settings
from bot.services.logging_service import logging_service

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- Prefix Commands ---
    @commands.command(name="say")
    @commands.has_permissions(administrator=True)
    async def say(self, ctx, *, text: str):
        """Bot repeats what the admin says. [Prefix Command]"""
        try:
            await ctx.message.delete()
            # Use allowed_mentions to prevent bot from pinging @everyone/@here by default
            await ctx.send(text, allowed_mentions=discord.AllowedMentions.none())
        except discord.Forbidden:
            await ctx.send("I don't have permission to delete your message.")

    # --- Slash Commands ---
    @app_commands.command(name="dmall", description="Send a broadcast message to all members of the server")
    @app_commands.checks.has_permissions(administrator=True)
    async def dm_all(self, interaction: discord.Interaction, message: str):
        """Sends a DM to all members of the server."""
        await interaction.response.defer(ephemeral=True)

        await interaction.followup.send("Starting to DM all members... This may take a while. I will notify you when finished.")

        count = 0
        failed = 0

        for member in interaction.guild.members:
            if member.bot:
                continue
            try:
                await member.send(message)
                count += 1
                # Rate limit protection
                await asyncio.sleep(0.5)
            except discord.Forbidden:
                failed += 1
            except Exception:
                failed += 1

        await interaction.followup.send(f"Finished DMing members. Success: {count}, Failed: {failed}")

    @app_commands.command(name="reload", description="Reloads a specific cog")
    @app_commands.checks.has_permissions(administrator=True)
    async def reload(self, interaction: discord.Interaction, cog_name: str):
        try:
            await self.bot.reload_extension(f"bot.cogs.{cog_name}")
            await interaction.response.send_message(f"✅ Reloaded cog `{cog_name}`", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to reload cog: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminCog(bot))

import asyncio # Added for sleep
