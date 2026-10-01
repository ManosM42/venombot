import discord
from bot.services.application_service import application_service
from bot.services.logging_service import logging_service
from bot.config.settings import settings

class ApplicationModal(discord.ui.Modal, title="Join the Team"):
    name = discord.ui.TextInput(label="Full Name", placeholder="Enter your name...", required=True)
    age = discord.ui.TextInput(label="Age", placeholder="How old are you?", required=True)
    exp = discord.ui.TextInput(label="Experience", style=discord.TextStyle.paragraph, placeholder="Previous experience...", required=True)
    reason = discord.ui.TextInput(label="Why join us?", style=discord.TextStyle.paragraph, placeholder="Tell us why...", required=True)
    extra = discord.ui.TextInput(label="Additional Info", style=discord.TextStyle.paragraph, placeholder="Anything else?", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        content = (
            f"**Name**: {self.name.value}\n"
            f"**Age**: {self.age.value}\n"
            f"**Experience**: {self.exp.value}\n"
            f"**Reason**: {self.reason.value}\n"
            f"**Extra**: {self.extra.value or 'N/A'}"
        )

        app_id, error = await application_service.submit_application(
            interaction.guild_id, interaction.user.id, content
        )

        if error:
            return await interaction.response.send_message(f"❌ {error}", ephemeral=True)

        await interaction.response.send_message("✅ Your application has been submitted! Staff will review it shortly.", ephemeral=True)

        # Send to review channel
        if settings.APPLICATION_REVIEW_CHANNEL_ID != 0:
            channel = interaction.guild.get_channel(settings.APPLICATION_REVIEW_CHANNEL_ID)
            if channel:
                embed = discord.Embed(title="📝 New Application", color=discord.Color.purple())
                embed.add_field(name="Applicant", value=f"{interaction.user.mention} ({interaction.user.id})")
                embed.add_field(name="Details", value=content, inline=False)
                embed.set_footer(text=f"Application ID: {app_id}")
                await channel.send(embed=embed, view=ApplicationReviewView(interaction.user.id, app_id))

class ApplicationReviewView(discord.ui.View):
    def __init__(self, user_id, app_id):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.app_id = app_id

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, custom_id="app_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Permission check
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("You don't have permission to do this.", ephemeral=True)

        await application_service.update_status(self.app_id, "accepted", interaction.user.id)

        user = interaction.guild.get_member(self.user_id)
        if user:
            try:
                await user.send("🎉 Your application has been **accepted**! Welcome to the team!")
            except:
                pass

        await interaction.response.edit_message(
            content=f"✅ Application {self.app_id} accepted by {interaction.user.mention}",
            view=None
        )

        await logging_service.log(
            category="Applications",
            message=f"Application {self.app_id} accepted.",
            user=user,
            guild=interaction.guild,
            color=discord.Color.green()
        )

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, custom_id="app_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("You don't have permission to do this.", ephemeral=True)

        await application_service.update_status(self.app_id, "denied", interaction.user.id)

        user = interaction.guild.get_member(self.user_id)
        if user:
            try:
                await user.send("❌ Your application has been **denied**. We wish you the best of luck!")
            except:
                pass

        await interaction.response.edit_message(
            content=f"❌ Application {self.app_id} rejected by {interaction.user.mention}",
            view=None
        )

        await logging_service.log(
            category="Applications",
            message=f"Application {self.app_id} rejected.",
            user=user,
            guild=interaction.guild,
            color=discord.Color.red()
        )
