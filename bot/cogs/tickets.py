import asyncio
import io
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# ───────────────────────── CONFIG ─────────────────────────
# Put these in your .env (role IDs are safest). If an ID is missing,
# the bot falls back to finding the role by name.
def env_int(name: str) -> int:
    try:
        return int(os.getenv(name, "0"))
    except ValueError:
        return 0

TICKET_CATEGORY_ID = env_int("TICKET_CATEGORY_ID")   # Discord category for tickets (optional)
LOG_CHANNEL_ID = env_int("LOG_CHANNEL_ID")           # transcripts (optional)
FOUNDER_ROLE_ID = env_int("FOUNDER_ROLE_ID")
COFOUNDER_ROLE_ID = env_int("COFOUNDER_ROLE_ID")
STAFF_ROLE_ID = env_int("STAFF_ROLE_ID")
BANNER_URL = os.getenv("PANEL_BANNER_URL", "")       # optional glass banner image
LOGO_URL = os.getenv("PANEL_LOGO_URL", "")           # optional thumbnail

BRAND = "Venom Shop"

# Glass palette: cool, translucent-looking tones
GLASS = 0x8FD3FF
GLASS_DARK = 0x2B3A55
GLASS_GREEN = 0x7CFFCB
GLASS_RED = 0xFF8FA3

SEP = "▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰"

CATEGORIES = {
    "owner": {
        "label": "Owner",
        "emoji": "👑",
        "desc_en": "Talk directly with the owner",
        "desc_el": "Επικοινωνία με τον Owner",
        "color": 0xFFD37A,
    },
    "purchase": {
        "label": "Purchase",
        "emoji": "🛒",
        "desc_en": "Buy something or get purchase help",
        "desc_el": "Αγορές και βοήθεια παραγγελίας",
        "color": 0x7CFFCB,
    },
    "application": {
        "label": "Application Accepted",
        "emoji": "📝",
        "desc_en": "Your application was accepted",
        "desc_el": "Η αίτησή σου έγινε δεκτή",
        "color": 0xB89CFF,
    },
    "question": {
        "label": "Question",
        "emoji": "💬",
        "desc_en": "Ask us anything",
        "desc_el": "Ρώτησέ μας οτιδήποτε",
        "color": 0x8FD3FF,
    },
}

LANGS = {
    "en": {"label": "English", "emoji": "🇬🇧"},
    "el": {"label": "Ελληνικά", "emoji": "🇬🇷"},
}

TEXT = {
    "en": {
        "welcome": "Welcome to your ticket",
        "body": "Please describe what you need. A member of our team will be with you shortly.",
        "info": "Ticket Info",
        "category": "Category",
        "opened_by": "Opened by",
        "language": "Language",
        "status": "Status",
        "open": "Open",
        "footer": "Only staff can close this ticket • you can cancel it any time",
        "close": "Close Ticket",
        "cancel": "Cancel Ticket",
        "closing": "🔒 Closing this ticket in **5 seconds**...",
        "cancelling": "🗑️ Ticket cancelled. Deleting in **5 seconds**...",
    },
    "el": {
        "welcome": "Καλώς ήρθες στο ticket σου",
        "body": "Περίγραψέ μας τι χρειάζεσαι. Κάποιο μέλος της ομάδας μας θα σε εξυπηρετήσει σύντομα.",
        "info": "Πληροφορίες Ticket",
        "category": "Κατηγορία",
        "opened_by": "Άνοιξε ο/η",
        "language": "Γλώσσα",
        "status": "Κατάσταση",
        "open": "Ανοιχτό",
        "footer": "Μόνο το staff κλείνει το ticket • μπορείς να το ακυρώσεις οποιαδήποτε στιγμή",
        "close": "Κλείσιμο",
        "cancel": "Ακύρωση",
        "closing": "🔒 Το ticket κλείνει σε **5 δευτερόλεπτα**...",
        "cancelling": "🗑️ Το ticket ακυρώθηκε. Διαγραφή σε **5 δευτερόλεπτα**...",
    },
}


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
    """Only Founder and Staff roles (plus admins) may close tickets."""
    if member.guild_permissions.administrator:
        return True
    founder, _cofounder, staff = get_roles(member.guild)
    allowed = {r.id for r in (founder, staff) if r}
    return any(r.id in allowed for r in member.roles)


def topic_owner_id(channel: discord.TextChannel):
    """Ticket owner ID is stored in the channel topic: 'ticket-owner:123'."""
    if channel.topic and channel.topic.startswith("ticket-owner:"):
        try:
            return int(channel.topic.split(":")[1].split("|")[0])
        except ValueError:
            return None
    return None


def get_logo(guild: discord.Guild):
    """Uses PANEL_LOGO_URL if set, otherwise the server icon."""
    if LOGO_URL:
        return LOGO_URL
    return guild.icon.url if guild.icon else None


def get_banner(guild: discord.Guild):
    """Uses PANEL_BANNER_URL if set, otherwise the server banner (needs boost level 2)."""
    if BANNER_URL:
        return BANNER_URL
    return guild.banner.url if guild.banner else None


def safe_name(text: str) -> str:
    cleaned = "".join(c for c in text.lower() if c.isalnum() or c in "-_")
    return cleaned[:30] or "user"


# ───────────────────────── TICKET CHANNEL VIEW ─────────────────────────
class TicketControlView(discord.ui.View):
    """Persistent: close (staff/founder only) + cancel (owner or staff)."""

    def __init__(self):
        super().__init__(timeout=None)

    def _lang(self, channel) -> str:
        if channel.topic and "|lang:" in channel.topic:
            return channel.topic.split("|lang:")[1][:2]
        return "en"

    @discord.ui.button(label="Close Ticket", emoji="🔒", style=discord.ButtonStyle.danger,
                       custom_id="venom:ticket:close")
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        lang = self._lang(channel)

        if not can_close(interaction.user):
            msg = ("❌ Only **Staff** and **Founder** can close tickets."
                   if lang == "en" else "❌ Μόνο το **Staff** και ο **Founder** κλείνουν tickets.")
            return await interaction.response.send_message(msg, ephemeral=True)

        try:
            await interaction.response.send_message(TEXT[lang]["closing"])
        except discord.NotFound:
            return  # interaction expired or already handled elsewhere
        await self._send_transcript(channel, interaction.user)
        await asyncio.sleep(5)
        try:
            await channel.delete(reason=f"Ticket closed by {interaction.user}")
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Cancel Ticket", emoji="🗑️", style=discord.ButtonStyle.secondary,
                       custom_id="venom:ticket:cancel")
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        lang = self._lang(channel)
        owner_id = topic_owner_id(channel)

        if interaction.user.id != owner_id and not can_close(interaction.user):
            msg = ("❌ Only the ticket owner or staff can cancel this."
                   if lang == "en" else "❌ Μόνο ο δημιουργός ή το staff μπορεί να ακυρώσει.")
            return await interaction.response.send_message(msg, ephemeral=True)

        try:
            await interaction.response.send_message(TEXT[lang]["cancelling"])
        except discord.NotFound:
            return  # interaction expired or already handled elsewhere
        await self._send_transcript(channel, interaction.user)
        await asyncio.sleep(5)
        try:
            await channel.delete(reason=f"Ticket cancelled by {interaction.user}")
        except discord.HTTPException:
            pass

    async def _send_transcript(self, channel: discord.TextChannel, closer: discord.Member):
        if not LOG_CHANNEL_ID:
            return
        log_channel = channel.guild.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return
        lines = []
        async for msg in channel.history(limit=None, oldest_first=True):
            content = msg.content or ""
            if msg.embeds and not content:
                content = "[embed]"
            lines.append(f"[{msg.created_at:%Y-%m-%d %H:%M}] {msg.author}: {content}")
        data = io.BytesIO("\n".join(lines).encode("utf-8"))
        embed = discord.Embed(
            title="📜 Ticket Transcript",
            description=f"{SEP}\n**Channel:** `{channel.name}`\n**Closed by:** {closer.mention}\n{SEP}",
            color=GLASS_DARK,
        )
        try:
            await log_channel.send(embed=embed, file=discord.File(data, filename=f"{channel.name}.txt"))
        except discord.HTTPException:
            pass


# ───────────────────────── STEP 2: LANGUAGE ─────────────────────────
class LanguageSelect(discord.ui.Select):
    def __init__(self, category_key: str):
        self.category_key = category_key
        options = [
            discord.SelectOption(label=v["label"], value=k, emoji=v["emoji"])
            for k, v in LANGS.items()
        ]
        super().__init__(placeholder="🌐 Choose your language / Επίλεξε γλώσσα",
                         options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await create_ticket(interaction, self.category_key, self.values[0])


class LanguageView(discord.ui.View):
    def __init__(self, category_key: str):
        super().__init__(timeout=180)
        self.add_item(LanguageSelect(category_key))


# ───────────────────────── STEP 1: CATEGORY ─────────────────────────
class CategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=v["label"], value=k, emoji=v["emoji"],
                                 description=v["desc_en"])
            for k, v in CATEGORIES.items()
        ]
        super().__init__(placeholder="✨ Choose a category...", options=options,
                         min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0]
        cat = CATEGORIES[key]
        embed = discord.Embed(
            title=f"{cat['emoji']}  {cat['label']}",
            description=(f"{SEP}\n\n**Step 2 of 2 — Language**\n"
                         "Choose the language for your ticket.\n"
                         "Επίλεξε τη γλώσσα του ticket σου.\n\n"
                         f"{SEP}"),
            color=cat["color"],
        )
        embed.set_footer(text=f"{BRAND} • Support")
        await interaction.response.edit_message(embed=embed, view=LanguageView(key))


class CategoryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(CategorySelect())


# ───────────────────────── PANEL ─────────────────────────
class TicketPanelView(discord.ui.View):
    """Persistent panel button — survives restarts, never gets lost."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open a Ticket", emoji="🎫", style=discord.ButtonStyle.primary,
                       custom_id="venom:ticket:open")
    async def open_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="💎  Open a Ticket",
            description=(f"{SEP}\n\n**Step 1 of 2 — Category**\n"
                         "Pick what best matches your request.\n\n"
                         + "\n".join(f"{v['emoji']} **{v['label']}** — {v['desc_en']}"
                                     for v in CATEGORIES.values())
                         + f"\n\n{SEP}"),
            color=GLASS,
        )
        embed.set_footer(text=f"{BRAND} • Support")
        await interaction.response.send_message(embed=embed, view=CategoryView(), ephemeral=True)


# ───────────────────────── CREATE TICKET ─────────────────────────
async def create_ticket(interaction: discord.Interaction, category_key: str, lang: str):
    guild = interaction.guild
    user = interaction.user
    cat = CATEGORIES[category_key]
    t = TEXT[lang]

    # One open ticket per user
    for ch in guild.text_channels:
        if topic_owner_id(ch) == user.id:
            msg = (f"❌ You already have an open ticket: {ch.mention}" if lang == "en"
                   else f"❌ Έχεις ήδη ανοιχτό ticket: {ch.mention}")
            return await interaction.response.edit_message(content=msg, embed=None, view=None)

    await interaction.response.edit_message(
        embed=discord.Embed(description="⏳ Creating your ticket...", color=GLASS), view=None
    )

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

    category = guild.get_channel(TICKET_CATEGORY_ID) if TICKET_CATEGORY_ID else None
    if category is not None and not isinstance(category, discord.CategoryChannel):
        category = None

    try:
        channel = await guild.create_text_channel(
            name=f"{cat['emoji']}┃{category_key}-{safe_name(user.name)}",
            category=category,
            overwrites=overwrites,
            topic=f"ticket-owner:{user.id}|lang:{lang}",
            reason=f"Ticket by {user}",
        )
    except discord.HTTPException:
        return await interaction.edit_original_response(
            embed=discord.Embed(description="❌ I couldn't create the ticket channel. Check my permissions.",
                                color=GLASS_RED))

    # Redirect the user to the ticket
    done = discord.Embed(
        title="✅  Ticket Created" if lang == "en" else "✅  Το Ticket Δημιουργήθηκε",
        description=f"{SEP}\n\n{channel.mention}\n\n{SEP}",
        color=GLASS_GREEN,
    )
    go = discord.ui.View()
    go.add_item(discord.ui.Button(
        label="Go to Ticket" if lang == "en" else "Μετάβαση στο Ticket",
        emoji="➡️", style=discord.ButtonStyle.link, url=channel.jump_url))
    await interaction.edit_original_response(embed=done, view=go)

    # Ticket info embed
    embed = discord.Embed(
        title=f"{cat['emoji']}  {t['welcome']}",
        description=(f"{SEP}\n\n{t['body']}\n\n{SEP}"),
        color=cat["color"],
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name=f"📂 {t['category']}", value=f"```{cat['label']}```", inline=True)
    embed.add_field(name=f"🌐 {t['language']}",
                    value=f"```{LANGS[lang]['label']}```", inline=True)
    embed.add_field(name=f"🟢 {t['status']}", value=f"```{t['open']}```", inline=True)
    embed.add_field(name=f"👤 {t['opened_by']}", value=user.mention, inline=False)
    embed.set_author(name=f"{BRAND} • {t['info']}", icon_url=get_logo(guild))
    embed.set_thumbnail(url=user.display_avatar.url)
    banner = get_banner(guild)
    if banner:
        embed.set_image(url=banner)
    embed.set_footer(text=t["footer"])

    # Ping: user, Founder, Staff Team, Co Founder
    pings = [user.mention] + [r.mention for r in (founder, staff, cofounder) if r]
    await channel.send(
        content=" ".join(pings),
        embed=embed,
        view=TicketControlView(),
        allowed_mentions=discord.AllowedMentions(users=True, roles=True),
    )


# ───────────────────────── COG ─────────────────────────
class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ticket-panel")
    @commands.has_permissions(administrator=True)
    async def ticket_panel(self, ctx: commands.Context):
        """Posts the permanent Venom Shop ticket panel."""
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        embed = discord.Embed(
            title=f"💎  {BRAND} — Support Center",
            description=(
                f"{SEP}\n\n"
                "✨ **Need help? We've got you.**\n"
                "Press the button below to open a private ticket with our team.\n\n"
                "🇬🇧 English  •  🇬🇷 Ελληνικά\n\n"
                + "\n".join(f"{v['emoji']} **{v['label']}**" for v in CATEGORIES.values())
                + f"\n\n{SEP}"
            ),
            color=GLASS,
        )
        embed.set_footer(text=f"{BRAND} • Average response: a few minutes")
        logo = get_logo(ctx.guild)
        banner = get_banner(ctx.guild)
        if logo:
            embed.set_thumbnail(url=logo)
        if banner:
            embed.set_image(url=banner)

        await ctx.send(embed=embed, view=TicketPanelView())

    @ticket_panel.error
    async def ticket_panel_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Administrator permission required.", delete_after=5)


async def setup(bot: commands.Bot):
    # Re-register persistent views on every start so the panel never dies
    bot.add_view(TicketPanelView())
    bot.add_view(TicketControlView())
    await bot.add_cog(Tickets(bot))
