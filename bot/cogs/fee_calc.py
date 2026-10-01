import json
import os

import aiohttp
import discord
from discord.ext import commands

# ───────────────────────── CONFIG ─────────────────────────
DATA_DIR = "bot/data"
FEE_FILE = os.path.join(DATA_DIR, "fee_settings.json")
DEFAULT_FEE = 1.0  # percent

BRAND = "Venom Shop"
GLASS = 0x8FD3FF
GLASS_GREEN = 0x7CFFCB
GLASS_RED = 0xFF8FA3
SEP = "▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰"

PRESET_FEES = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 5.0]

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=eur"


# ───────────────────────── PERSISTENCE ─────────────────────────
def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def get_fee() -> float:
    _ensure_data_dir()
    if not os.path.exists(FEE_FILE):
        return DEFAULT_FEE
    try:
        with open(FEE_FILE, "r") as f:
            return float(json.load(f).get("fee_percent", DEFAULT_FEE))
    except (json.JSONDecodeError, ValueError, OSError):
        return DEFAULT_FEE


def set_fee(percent: float):
    _ensure_data_dir()
    with open(FEE_FILE, "w") as f:
        json.dump({"fee_percent": percent}, f)


# ───────────────────────── PRICE FETCH ─────────────────────────
async def get_btc_eur_price() -> float | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(COINGECKO_URL, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return float(data["bitcoin"]["eur"])
    except (aiohttp.ClientError, KeyError, ValueError, TypeError):
        return None


# ───────────────────────── CALCULATION ─────────────────────────
def calculate(amount: float, direction: str, price: float, fee_percent: float):
    """
    direction: 'eur_to_btc' or 'btc_to_eur'
    Fee is taken from the input amount before conversion.
    Returns: (fee_amount, net_amount, result, net_unit, fee_unit)
    """
    fee_amount = amount * (fee_percent / 100)
    net_amount = amount - fee_amount

    if direction == "eur_to_btc":
        result = net_amount / price
        return fee_amount, net_amount, result, "EUR", "EUR"
    else:
        result = net_amount * price
        return fee_amount, net_amount, result, "BTC", "BTC"


# ───────────────────────── MODAL ─────────────────────────
class AmountModal(discord.ui.Modal):
    def __init__(self, direction: str):
        title = "EUR → BTC" if direction == "eur_to_btc" else "BTC → EUR"
        super().__init__(title=f"💱 {title}")
        self.direction = direction
        unit = "EUR" if direction == "eur_to_btc" else "BTC"
        self.amount = discord.ui.TextInput(
            label=f"Amount in {unit}",
            placeholder=f"e.g. {'100' if unit == 'EUR' else '0.01'}",
            required=True,
            max_length=20,
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.amount.value.replace(",", ".").strip()
        try:
            amount = float(raw)
            if amount <= 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                "❌ Please enter a valid positive number.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True, thinking=True)

        price = await get_btc_eur_price()
        if price is None:
            return await interaction.followup.send(
                "❌ Couldn't fetch the live BTC price right now. Try again in a moment.",
                ephemeral=True,
            )

        fee_percent = get_fee()
        fee_amount, net_amount, result, fee_unit, _ = calculate(
            amount, self.direction, price, fee_percent
        )

        if self.direction == "eur_to_btc":
            title = "💶  EUR → ₿ BTC"
            in_label, in_val = "Amount", f"€{amount:,.2f}"
            fee_label = f"Fee ({fee_percent:g}%)"
            fee_val = f"€{fee_amount:,.2f}"
            net_label = "Net amount"
            net_val = f"€{net_amount:,.2f}"
            out_label = "You receive"
            out_val = f"₿ {result:.8f}"
        else:
            title = "₿  BTC → 💶 EUR"
            in_label, in_val = "Amount", f"₿ {amount:.8f}"
            fee_label = f"Fee ({fee_percent:g}%)"
            fee_val = f"₿ {fee_amount:.8f}"
            net_label = "Net amount"
            net_val = f"₿ {net_amount:.8f}"
            out_label = "You receive"
            out_val = f"€{result:,.2f}"

        embed = discord.Embed(
            title=title,
            description=f"{SEP}\n\n**Live rate:** 1 BTC = €{price:,.2f}\n\n{SEP}",
            color=GLASS_GREEN,
        )
        embed.add_field(name=f"📥 {in_label}", value=f"```{in_val}```", inline=True)
        embed.add_field(name=f"💸 {fee_label}", value=f"```{fee_val}```", inline=True)
        embed.add_field(name=f"🧾 {net_label}", value=f"```{net_val}```", inline=True)
        embed.add_field(name=f"✅ {out_label}", value=f"```{out_val}```", inline=False)
        embed.set_footer(text=f"{BRAND} • Fee Calculator • for calculation purposes only")

        await interaction.followup.send(embed=embed, ephemeral=True)


# ───────────────────────── PANEL VIEW ─────────────────────────
class FeeCalcView(discord.ui.View):
    """Persistent panel — survives restarts."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="EUR → BTC", emoji="💶", style=discord.ButtonStyle.primary,
                       custom_id="venom:feecalc:eur_to_btc")
    async def eur_to_btc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AmountModal("eur_to_btc"))

    @discord.ui.button(label="BTC → EUR", emoji="🪙", style=discord.ButtonStyle.success,
                       custom_id="venom:feecalc:btc_to_eur")
    async def btc_to_eur(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AmountModal("btc_to_eur"))


# ───────────────────────── SET-FEE UI ─────────────────────────
class CustomFeeModal(discord.ui.Modal, title="⚙️ Custom Fee"):
    fee_input = discord.ui.TextInput(
        label="Fee percentage (e.g. 1.75)",
        placeholder="1.75",
        required=True,
        max_length=6,
    )

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.fee_input.value.replace(",", ".").replace("%", "").strip()
        try:
            percent = float(raw)
            if not (0 <= percent <= 100):
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                "❌ Enter a number between 0 and 100.", ephemeral=True
            )

        set_fee(percent)
        embed = discord.Embed(
            title="✅ Fee Updated",
            description=f"{SEP}\n\nNew transaction fee: **{percent:g}%**\n\n{SEP}",
            color=GLASS_GREEN,
        )
        embed.set_footer(text=f"{BRAND} • applies automatically to !fee-cal")
        await interaction.response.edit_message(embed=embed, view=None)


class FeePresetSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=f"{p:g}%", value=str(p), emoji="💸")
            for p in PRESET_FEES
        ]
        super().__init__(placeholder="Choose a preset fee %...", options=options,
                         min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        percent = float(self.values[0])
        set_fee(percent)
        embed = discord.Embed(
            title="✅ Fee Updated",
            description=f"{SEP}\n\nNew transaction fee: **{percent:g}%**\n\n{SEP}",
            color=GLASS_GREEN,
        )
        embed.set_footer(text=f"{BRAND} • applies automatically to !fee-cal")
        await interaction.response.edit_message(embed=embed, view=None)


class SetFeeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(FeePresetSelect())

    @discord.ui.button(label="Custom %", emoji="⚙️", style=discord.ButtonStyle.secondary)
    async def custom_fee(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CustomFeeModal())


# ───────────────────────── COG ─────────────────────────
class FeeCalc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="fee-cal")
    async def fee_cal(self, ctx: commands.Context):
        """Opens the EUR/BTC fee calculator panel."""
        fee_percent = get_fee()
        price = await get_btc_eur_price()
        price_line = f"1 BTC ≈ €{price:,.2f}" if price else "Live price unavailable right now"

        embed = discord.Embed(
            title="💱  Venom Shop — Fee Calculator",
            description=(
                f"{SEP}\n\n"
                "Choose a direction below to calculate your exchange.\n\n"
                f"🔹 **Current fee:** `{fee_percent:g}%`\n"
                f"🔹 **Rate:** {price_line}\n\n"
                f"{SEP}"
            ),
            color=GLASS,
        )
        embed.set_footer(text=f"{BRAND} • Calculator only — no funds are moved")
        await ctx.send(embed=embed, view=FeeCalcView())

    @commands.command(name="set-fee")
    @commands.has_permissions(administrator=True)
    async def set_fee_cmd(self, ctx: commands.Context):
        """Admin only: set the transaction fee percentage."""
        current = get_fee()
        embed = discord.Embed(
            title="⚙️  Set Transaction Fee",
            description=(
                f"{SEP}\n\n"
                f"**Current fee:** `{current:g}%`\n\n"
                "Pick a preset below, or press **Custom %** to type your own.\n\n"
                f"{SEP}"
            ),
            color=GLASS,
        )
        embed.set_footer(text=f"{BRAND} • this applies to all future !fee-cal calculations")
        await ctx.send(embed=embed, view=SetFeeView())

    @set_fee_cmd.error
    async def set_fee_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Administrator permission required.", delete_after=5)


async def setup(bot: commands.Bot):
    bot.add_view(FeeCalcView())
    await bot.add_cog(FeeCalc(bot))
