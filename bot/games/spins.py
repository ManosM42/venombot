
import random
import discord
from discord.ext import commands

from bot.services.economy_service import economy_service


SUITS = ["♠️", "♥️", "♦️", "♣️"]
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]


def card_value(cards):

    total = 0
    aces = 0

    for card in cards:

        rank = card[:-2]

        if rank in ["J", "Q", "K"]:
            total += 10

        elif rank == "A":
            total += 11
            aces += 1

        else:
            total += int(rank)

    while total > 21 and aces:

        total -= 10
        aces -= 1

    return total


def format_cards(cards):

    return "  ".join(cards)


class BlackjackView(discord.ui.View):

    def __init__(
        self,
        cog,
        ctx,
        bet,
        player_cards,
        dealer_cards
    ):

        super().__init__(timeout=120)

        self.cog = cog
        self.ctx = ctx
        self.bet = bet

        self.player_cards = player_cards
        self.dealer_cards = dealer_cards

        self.finished = False

    async def interaction_check(self, interaction):

        if interaction.user.id != self.ctx.author.id:

            await interaction.response.send_message(
                "❌ Αυτό το Blackjack δεν είναι δικό σου.",
                ephemeral=True
            )

            return False

        return True

    @discord.ui.button(
        label="HIT",
        emoji="🎴",
        style=discord.ButtonStyle.primary
    )
    async def hit(
        self,
        interaction,
        button
    ):

        self.player_cards.append(
            self.cog.draw_card()
        )

        value = card_value(
            self.player_cards
        )

        if value > 21:

            await self.finish(
                interaction,
                "LOSE"
            )

            return

        if value == 21:

            await self.stand(
                interaction,
                button
            )

            return

        await interaction.response.edit_message(
            embed=self.cog.create_embed(self),
            view=self
        )

    @discord.ui.button(
        label="STAND",
        emoji="🛑",
        style=discord.ButtonStyle.success
    )
    async def stand(
        self,
        interaction,
        button
    ):

        while card_value(
            self.dealer_cards
        ) < 17:

            self.dealer_cards.append(
                self.cog.draw_card()
            )

        player = card_value(
            self.player_cards
        )

        dealer = card_value(
            self.dealer_cards
        )

        if dealer > 21:

            result = "WIN"

        elif player > dealer:

            result = "WIN"

        elif player == dealer:

            result = "PUSH"

        else:

            result = "LOSE"

        await self.finish(
            interaction,
            result
        )

    async def finish(
        self,
        interaction,
        result
    ):

        if self.finished:
            return

        self.finished = True

        for child in self.children:
            child.disabled = True

        guild_id = self.ctx.guild.id

        if result == "BLACKJACK":

            payout = int(
                self.bet * 2.5
            )

            await economy_service.add_coins(
                guild_id,
                self.ctx.author.id,
                payout,
                "BLACKJACK_WIN"
            )

            message = (
                "🃏 **BLACKJACK!**\n"
                f"💰 Payout: **{payout:,} coins**"
            )

        elif result == "WIN":

            payout = self.bet * 2

            await economy_service.add_coins(
                guild_id,
                self.ctx.author.id,
                payout,
                "BLACKJACK_WIN"
            )

            message = (
                "🏆 **YOU WIN!**\n"
                f"💰 Payout: **{payout:,} coins**"
            )

        elif result == "PUSH":

            await economy_service.add_coins(
                guild_id,
                self.ctx.author.id,
                self.bet,
                "BLACKJACK_PUSH"
            )

            message = (
                "🤝 **PUSH**\n"
                f"💰 Returned: **{self.bet:,} coins**"
            )

        else:

            message = (
                "💀 **DEALER WINS**\n"
                f"💸 Lost: **{self.bet:,} coins**"
            )

        embed = self.cog.create_embed(
            self,
            reveal=True
        )

        embed.title = "🏁 BLACKJACK • FINISHED"

        embed.add_field(
            name="Result",
            value=message,
            inline=False
        )

        await interaction.response.edit_message(
            embed=embed,
            view=self
        )

        self.stop()

    async def on_timeout(self):

        if self.finished:
            return

        self.finished = True

        for child in self.children:
            child.disabled = True


class Blackjack(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    def draw_card(self):

        rank = random.choice(RANKS)
        suit = random.choice(SUITS)

        return rank + suit

    def create_embed(
        self,
        view,
        reveal=False
    ):

        player_value = card_value(
            view.player_cards
        )

        if reveal:

            dealer_text = format_cards(
                view.dealer_cards
            )

            dealer_value = card_value(
                view.dealer_cards
            )

        else:

            dealer_text = (
                view.dealer_cards[0]
                + "  🂠"
            )

            dealer_value = "?"

        embed = discord.Embed(
            title="🃏 BLACKJACK",
            description=(
                f"### 🎩 Dealer\n"
                f"`{dealer_text}`\n"
                f"Value: **{dealer_value}**\n\n"
                f"### 👤 {view.ctx.author.display_name}\n"
                f"`{format_cards(view.player_cards)}`\n"
                f"Value: **{player_value}**\n\n"
                f"💰 **Bet:** {view.bet:,} coins"
            ),
            color=discord.Color.gold()
        )

        embed.set_footer(
            text="Viper Project • Blackjack"
        )

        return embed

    @commands.command(
        name="bj",
        aliases=["blackjack"]
    )
    async def blackjack(
        self,
        ctx,
        bet: int = None
    ):

        if ctx.guild is None:
            return

        if bet is None:

            await ctx.send(
                "🃏 **BLACKJACK**\n\n"
                "Χρήση: `!bj 100`"
            )

            return

        if bet <= 0:

            await ctx.send(
                "❌ Το bet πρέπει να είναι μεγαλύτερο από 0."
            )

            return

        balance = await economy_service.get_balance(
            ctx.guild.id,
            ctx.author.id
        )

        if balance < bet:

            await ctx.send(
                f"❌ Δεν έχεις αρκετά coins.\n"
                f"💰 Balance: **{balance:,}**"
            )

            return

        success = await economy_service.spend_coins(
            ctx.guild.id,
            ctx.author.id,
            bet,
            "BLACKJACK_BET"
        )

        if not success:

            await ctx.send(
                "❌ Δεν μπόρεσα να αφαιρέσω το bet."
            )

            return

        player_cards = [
            self.draw_card(),
            self.draw_card()
        ]

        dealer_cards = [
            self.draw_card(),
            self.draw_card()
        ]

        view = BlackjackView(
            self,
            ctx,
            bet,
            player_cards,
            dealer_cards
        )

        player_value = card_value(
            player_cards
        )

        if player_value == 21:

            message = await ctx.send(
                embed=self.create_embed(
                    view,
                    reveal=True
                )
            )

            await view.finish(
                FakeInteraction(message),
                "BLACKJACK"
            )

            return

        await ctx.send(
            embed=self.create_embed(view),
            view=view
        )


class FakeInteraction:

    def __init__(self, message):
        self.message = message

    async def response_edit(self, *args, **kwargs):
        pass


async def setup(bot):

    await bot.add_cog(
        Blackjack(bot)
    )
