import discord
from bot.services.ticket_service import ticket_service
from bot.services.logging_service import logging_service
from bot.config.settings import settings

class TicketCategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Support", description="General technical support", emoji="🛠️"),
            discord.SelectOption(label="Billing", description="Payment and billing issues", emoji="💰"),
            discord.SelectOption(label="Partnership", description="Business partnerships", emoji="📩"),
            discord.SelectOption(label="Report", description="Report a user or bug", emoji="🚨"),
            discord.SelectOption(label="Other", description="Anything else", emoji="❓"),
        ]
        super().__init__(placeholder="Choose a ticket category...", options=options, custom_id="ticket_category_select")

    async def callback(self, interaction: discord.Interaction):
        # Now open a modal for the issue
        await interaction.response.send_modal(TicketIssueModal(self.values[0]))

class TicketIssueModal(discord.ui.Modal):
    def __init__(self, category):
        super().__init__(title=f"Ticket: {category}")
        self.category = category
        self.issue = discord.ui.TextInput(
            label="What is the issue?",
            style=discord.TextStyle.paragraph,
            placeholder="Describe your problem in detail...",
            required=True,
            max_length=1000
        )

    async def on_submit(self, interaction: discord.Interaction):
        channel, ticket_id = await ticket_service.create_ticket(
            interaction.guild, interaction.user, self.category, self.issue.value
        )

        await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)

        embed = discord.Embed(
            title="🎫 Support Ticket",
            description=f"**Ticket ID:** `{ticket_id}`\n**Category:** {self.category}\n**Opened by:** {interaction.user.mention}\n\n**Issue:**\n{self.issue.value}",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Staff will be with you shortly. Use the buttons below to manage the ticket.")
        await channel.send(embed=embed, view=TicketControlView(ticket_id))

class TicketControlView(discord.ui.View):
    def __init__(self, ticket_id):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Permission check (Staff only)
        if not interaction.user.guild_permissions.administrator:
             return await interaction.response.send_message("Only staff can close tickets.", ephemeral=True)

        await interaction.response.send_message("Closing ticket and generating transcript...", ephemeral=False)

        # Generate transcript (simple version for now)
        messages = []
        async for msg in interaction.channel.history(limit=None, oldest_first=True):
            messages.append(f"[{msg.created_at.strftime('%Y-%m-%d %H:%M')}] {msg.author}: {msg.content}")

        transcript = "\n".join(messages)

        await ticket_service.close_ticket(self.ticket_id, "Closed by staff")

        # Send transcript to log channel
        if settings.LOG_CHANNEL_ID != 0:
            log_channel = interaction.guild.get_channel(settings.LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(f"📜 **Transcript for Ticket {self.ticket_id}**\n```\n{transcript[:1900]}\n```")

        await interaction.channel.delete()

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.success, custom_id="ticket_claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
             return await interaction.response.send_message("Only staff can claim tickets.", ephemeral=True)

        await ticket_service.claim_ticket(self.ticket_id, interaction.user.id)
        await interaction.response.send_message(f"✅ This ticket has been claimed by {interaction.user.mention}", ephemeral=False)

class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket 🎫", style=discord.ButtonStyle.primary, custom_id="ticket_open")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Please select a category first:", view=TicketCategoryView(), ephemeral=True)

class TicketCategoryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketCategorySelect())
