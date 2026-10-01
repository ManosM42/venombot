import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# ───────────────────────── CONFIG ─────────────────────────
def env_int(name: str) -> int:
    try:
        return int(os.getenv(name, "0"))
    except ValueError:
        return 0

EXCHANGE_CATEGORY_ID = env_int("EXCHANGE_CATEGORY_ID")   # optional Discord category
LOG_CHANNEL_ID = env_int("LOG_CHANNEL_ID")                # reuse same log channel as tickets
FOUNDER_ROLE_ID = env_int("FOUNDER_ROLE_ID")
COFOUNDER_ROLE_ID = env_int("COFOUNDER_ROLE_ID")
STAFF_ROLE_ID = env_int("STAFF_ROLE_ID")

BRAND = "Venom Shop"
GLASS = 0x8FD3FF
GLASS_GREEN = 0x7CFFCB
GLASS_RED = 0xFF8FA3
SEP = "▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰"


# ───────────────────────── HELPERS ─────────────────────────
def find_role(guild: discord.Guild, role_id: int, *names: str):
    if role_id:
        role = guild.get_role(role_id)
        if role:
            return role
    lowered = [n.lower() for n in names]
    for role in guild.roles:
        clean = role.name.lower().strip()
        if any(clean == n or clean.startswith(n) for n in lowered):
            return role
    return None


def get_roles(guild: discord.Guild):
    founder = find_role(guild, FOUNDER_ROLE_ID, "founder")
    cofounder = find_role(guild, COFOUNDER_ROLE_ID, "co founder", "co-founder", "cofounder")
    staff = find_role(guild, STAFF_ROLE_ID, "staff team", "staff")
    return founder, cofounder, staff


def can_close(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    founder, _cofounder, staff = get_roles(member.guild)
    allowed = {r.id for r in (founder, staff) if r}
    return any(r.id in allowed for r in member.roles)


def topic_owner_id(channel: discord.TextChannel):
    if channel.topic and channel.topic.startswith("exchange-owner:"):
        try:
            return int(channel.topic.split(":")[1])
        except ValueError:
            return None
    return None


def safe_name(text: str) -> str:
    cleaned = "".join(c for c in text.lower() if c.isalnum() or c in "-_")
    return cleaned[:30] or "user"


# ───────────────────────── FORM ─────────────────────────
class ExchangeModal(discord.ui.Modal, title="💱 Start Exchange"):
    payment_method = discord.ui.TextInput(
        label="Payment Method",
        placeholder="e.g. PayPal, Bank Transfer, Card...",
        required=True,
        max_length=100,
    )
    how_much = discord.ui.TextInput(
        label="How Much",
        placeholder="e.g. 100 EUR or 0.01 BTC",
        required=True,
        max_length=50,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await create_exchange_ticket(interaction, self.payment_method.value, self.how_much.value)


# ───────────────────────── TICKET CONTROLS ─────────────────────────
class ExchangeControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close", emoji="🔒", style=discord.ButtonStyle.danger,
                       custom_id="venom:exchange:close")
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not can_close(interaction.user):
            return await interaction.response.send_message(
                "❌ Only **Staff** and **Founder** can close this.", ephemeral=True
            )
        try:
            await interaction.response.send_message("🔒 Closing in **5 seconds**...")
        except discord.NotFound:
            return
        await self._log_close(interaction.channel, interaction.user)
        import asyncio
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Exchange ticket closed by {interaction.user}")
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Cancel", emoji="🗑️", style=discord.ButtonStyle.secondary,
                       custom_id="venom:exchange:cancel")
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        owner_id = topic_owner_id(interaction.channel)
        if interaction.user.id != owner_id and not can_close(interaction.user):
            return await interaction.response.send_message(
                "❌ Only the ticket owner or staff can cancel this.", ephemeral=True
            )
        try:
            await interaction.response.send_message("🗑️ Cancelling in **5 seconds**...")
        except discord.NotFound:
            return
        await self._log_close(interaction.channel, interaction.user)
        import asyncio
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Exchange ticket cancelled by {interaction.user}")
        except discord.HTTPException:
            pass

    async def _log_close(self, channel: discord.TextChannel, closer: discord.Member):
        if not LOG_CHANNEL_ID:
            return
        log_channel = channel.guild.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return
        embed = discord.Embed(
            title="📜 Exchange Ticket Closed",
            description=f"**Channel:** `{channel.name}`\n**Closed by:** {closer.mention}",
            color=GLASS_RED,
        )
        try:
            await log_channel.send(embed=embed)
        except discord.HTTPException:
            pass


# ───────────────────────── PANEL ─────────────────────────
class ExchangePanelView(discord.ui.View):
    """Persistent panel button — survives restarts."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Start Exchange", emoji="💱", style=discord.ButtonStyle.primary,
                       custom_id="venom:exchange:start")
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ExchangeModal())


# ───────────────────────── CREATE TICKET ─────────────────────────
async def create_exchange_ticket(interaction: discord.Interaction, payment_method: str, how_much: str):
    guild = interaction.guild
    user = interaction.user

    for ch in guild.text_channels:
        if topic_owner_id(ch) == user.id:
            return await interaction.response.send_message(
                f"❌ You already have an open exchange ticket: {ch.mention}", ephemeral=True
            )

    await interaction.response.defer(ephemeral=True, thinking=True)

    founder, cofounder, staff = get_roles(guild)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                          read_message_history=True, attach_files=True,
                                          embed_links=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                              read_message_history=True, manage_channels=True,
                                              manage_messages=True, embed_links=True,
                                              attach_files=True),
    }
    for role in (founder, cofounder, staff):
        if role:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                                           read_message_history=True,
                                                           attach_files=True, embed_links=True)

    category = guild.get_channel(EXCHANGE_CATEGORY_ID) if EXCHANGE_CATEGORY_ID else None
    if category is not None and not isinstance(category, discord.CategoryChannel):
        category = None

    try:
        channel = await guild.create_text_channel(
            name=f"exchanges-{safe_name(user.name)}",
            category=category,
            overwrites=overwrites,
            topic=f"exchange-owner:{user.id}",
            reason=f"Exchange ticket by {user}",
        )
    except discord.HTTPException:
        return await interaction.followup.send(
            "❌ I couldn't create the ticket channel. Check my permissions.", ephemeral=True
        )

    go = discord.ui.View()
    go.add_item(discord.ui.Button(label="Go to Ticket", emoji="➡️",
                                  style=discord.ButtonStyle.link, url=channel.jump_url))
    await interaction.followup.send(
        embed=discord.Embed(
            title="✅ Exchange Ticket Created",
            description=f"{channel.mention}",
            color=GLASS_GREEN,
        ),
        view=go,
        ephemeral=True,
    )

    embed = discord.Embed(
        title="💱  Exchanges",
        description=f"{SEP}\n\nNew exchange request from {user.mention}\n\n{SEP}",
        color=GLASS,
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="💳 Payment Method", value=f"```{payment_method}```", inline=True)
    embed.add_field(name="💰 How Much", value=f"```{how_much}```", inline=True)
    embed.set_author(name=f"{BRAND} • Exchange")
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text="Staff will process your exchange shortly.")

    pings = [user.mention] + [r.mention for r in (founder, staff, cofounder) if r]
    await channel.send(
        content=" ".join(pings),
        embed=embed,
        view=ExchangeControlView(),
        allowed_mentions=discord.AllowedMentions(users=True, roles=True),
    )


# ───────────────────────── COG ─────────────────────────
class ExchangeTickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="exchange-panel")
    @commands.has_permissions(administrator=True)
    async def exchange_panel(self, ctx: commands.Context):
        """Posts the permanent Exchanges panel."""
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        embed = discord.Embed(
            title="💱  Venom Shop — Exchanges",
            description=(
                f"{SEP}\n\n"
                "Want to make an exchange?\n"
                "Press **Start Exchange** and fill in the quick form.\n\n"
                f"{SEP}"
            ),
            color=GLASS,
        )
        embed.set_footer(text=f"{BRAND} • Exchanges")
        await ctx.send(embed=embed, view=ExchangePanelView())

    @exchange_panel.error
    async def exchange_panel_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Administrator permission required.", delete_after=5)


async def setup(bot: commands.Bot):
    bot.add_view(ExchangePanelView())
    bot.add_view(ExchangeControlView())
    await bot.add_cog(ExchangeTickets(bot))