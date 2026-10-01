import discord
from discord import app_commands
from discord.ext import commands
from bot.services.application_service import application_service
from bot.views.application_views import ApplicationModal
from bot.config.settings import settings

class ApplicationsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="apply", description="Start the application process")
    async def apply(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ApplicationModal())

    @app_commands.command(name="panel", description="Setup the application panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🚀 Join Our Team",
            description="Click the button below to start your application process!",
            color=discord.Color.purple()
        )
        view = discord.ui.View(timeout=None)
        btn = discord.ui.Button(label="Apply Now 📝", style=discord.ButtonStyle.primary, custom_id="apply_btn")

        async def apply_callback(interaction):
            await interaction.response.send_modal(ApplicationModal())

        btn.callback = apply_callback
        view.add_item(btn)

        await interaction.response.send_message("Application panel sent.", ephemeral=True)
        await interaction.channel.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(ApplicationsCog(bot))
