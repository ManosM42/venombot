import random
import discord
from discord.ext import commands
from dataclasses import dataclass

from bot.services.economy_service import economy_service
from bot.config.settings import settings


# =================================================================
# TIC-TAC-TOE
# =================================================================

@dataclass
class TTTGame:
    guild_id: int
    challenger: discord.abc.User
    opponent: discord.abc.User
    wager: int
    vs_bot: bool

    board: list
    current_player_id: int

    finished: bool = False


WIN_COMBOS = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
]


def check_winner(board):
    for a, b, c in WIN_COMBOS:
        if board[a] != "⬜" and board[a] == board[b] == board[c]:
            return board[a]
    if "⬜" not in board:
        return "DRAW"
    return None


def bot_pick_move(board, bot_symbol, human_symbol):
    empty = [i for i, v in enumerate(board) if v == "⬜"]

    # Try to win
    for i in empty:
        test = board.copy()
        test[i] = bot_symbol
        if check_winner(test) == bot_symbol:
            return i

    # Block human win
    for i in empty:
        test = board.copy()
        test[i] = human_symbol
        if check_winner(test) == human_symbol:
            return i

    # Take center
    if 4 in empty:
        return 4

    # Take a corner
    corners = [c for c in (0, 2, 6, 8) if c in empty]
    if corners:
        return random.choice(corners)

    return random.choice(empty)


class TicTacToeView(discord.ui.View):

    def __init__(self, cog, game: TTTGame):
        super().__init__(timeout=180)
        self.cog = cog
        self.game = game

        for index in range(9):
            button = discord.ui.Button(
                label=" ", emoji="⬜", style=discord.ButtonStyle.secondary, row=index // 3
            )
            button.callback = self.create_callback(index)
            self.add_item(button)

    def create_callback(self, index):
        async def callback(interaction: discord.Interaction):
            game = self.game

            if interaction.user.id not in (game.challenger.id, game.opponent.id):
                return await interaction.response.send_message(
                    "❌ Δεν συμμετέχεις σε αυτή την παρτίδα.", ephemeral=True
                )

            if interaction.user.id != game.current_player_id:
                return await interaction.response.send_message(
                    "⏳ Δεν είναι η σειρά σου.", ephemeral=True
                )

            if game.board[index] != "⬜":
                return await interaction.response.send_message(
                    "❌ Αυτή η θέση είναι ήδη πιασμένη.", ephemeral=True
                )

            symbol = "❌" if interaction.user.id == game.challenger.id else "⭕"
            game.board[index] = symbol

            button = self.children[index]
            button.emoji = symbol
            button.label = " "
            button.disabled = True

            result = check_winner(game.board)
            if result:
                game.finished = True
                await self.cog.finish_ttt(interaction, game, result, self)
                self.stop()
                return

            # Switch turn
            game.current_player_id = (
                game.opponent.id if interaction.user.id == game.challenger.id else game.challenger.id
            )

            embed = self.cog.create_ttt_embed(game)
            await interaction.response.edit_message(embed=embed, view=self)

            # If it's now the bot's turn, play automatically
            if game.vs_bot and game.current_player_id == game.opponent.id:
                await self.play_bot_turn(interaction, game)

        return callback

    async def play_bot_turn(self, interaction, game: TTTGame):
        move = bot_pick_move(game.board, "⭕", "❌")
        game.board[move] = "⭕"

        button = self.children[move]
        button.emoji = "⭕"
        button.label = " "
        button.disabled = True

        result = check_winner(game.board)
        if result:
            game.finished = True
            await self.cog.finish_ttt(interaction, game, result, self, use_followup=True)
            self.stop()
            return

        game.current_player_id = game.challenger.id
        embed = self.cog.create_ttt_embed(game)
        await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)

    async def on_timeout(self):
        if self.game.finished:
            return
        self.game.finished = True
        for child in self.children:
            child.disabled = True

        if self.game.wager > 0:
            await economy_service.add_coins(
                self.game.guild_id, self.game.challenger.id, self.game.wager, "TTT_TIMEOUT_REFUND"
            )
            if not self.game.vs_bot:
                await economy_service.add_coins(
                    self.game.guild_id, self.game.opponent.id, self.game.wager, "TTT_TIMEOUT_REFUND"
                )


class ChallengeView(discord.ui.View):
    """Confirmation view when challenging a human opponent with a wager."""

    def __init__(self, cog, ctx, opponent, wager):
        super().__init__(timeout=60)
        self.cog = cog
        self.ctx = ctx
        self.opponent = opponent
        self.wager = wager

    @discord.ui.button(label="Accept", emoji="✅", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message(
                "❌ Μόνο ο αντίπαλος μπορεί να αποδεχτεί.", ephemeral=True
            )

        guild_id = self.ctx.guild.id

        if self.wager > 0:
            opponent_balance = await economy_service.get_balance(guild_id, self.opponent.id)
            if opponent_balance < self.wager:
                return await interaction.response.send_message(
                    f"❌ Δεν έχεις αρκετά coins. Υπόλοιπο: **{opponent_balance:,}**.", ephemeral=True
                )

            if not await economy_service.spend_coins(guild_id, self.ctx.author.id, self.wager, "TTT_WAGER"):
                return await interaction.response.send_message(
                    "❌ Το ποντάρισμα του challenger δεν είναι πλέον διαθέσιμο.", ephemeral=True
                )

            if not await economy_service.spend_coins(guild_id, self.opponent.id, self.wager, "TTT_WAGER"):
                await economy_service.add_coins(guild_id, self.ctx.author.id, self.wager, "TTT_REFUND")
                return await interaction.response.send_message(
                    "❌ Δεν μπόρεσα να κλειδώσω το δεύτερο ποντάρισμα.", ephemeral=True
                )

        game = TTTGame(
            guild_id=guild_id,
            challenger=self.ctx.author,
            opponent=self.opponent,
            wager=self.wager,
            vs_bot=False,
            board=["⬜"] * 9,
            current_player_id=self.ctx.author.id,
        )

        self.cog.games[guild_id] = game
        self.stop()

        game_view = TicTacToeView(self.cog, game)
        embed = self.cog.create_ttt_embed(game)
        await interaction.response.edit_message(content=None, embed=embed, view=game_view)

    @discord.ui.button(label="Decline", emoji="❌", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message(
                "❌ Μόνο ο αντίπαλος μπορεί να απαντήσει.", ephemeral=True
            )
        self.stop()
        await interaction.response.edit_message(content="❌ Η πρόκληση απορρίφθηκε.", embed=None, view=None)


class TTTStartView(discord.ui.View):
    """Shown when `!ttt` is used with no opponent — lets the user pick vs Bot."""

    def __init__(self, cog, ctx):
        super().__init__(timeout=30)
        self.cog = cog
        self.ctx = ctx

    @discord.ui.button(label="Play vs Bot", emoji="🤖", style=discord.ButtonStyle.primary)
    async def vs_bot(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Δεν είναι δικό σου game.", ephemeral=True)

        guild_id = self.ctx.guild.id
        if guild_id in self.cog.games:
            return await interaction.response.send_message(
                "❌ Υπάρχει ήδη ενεργή παρτίδα σε αυτόν τον server.", ephemeral=True
            )

        game = TTTGame(
            guild_id=guild_id,
            challenger=self.ctx.author,
            opponent=interaction.client.user,
            wager=0,
            vs_bot=True,
            board=["⬜"] * 9,
            current_player_id=self.ctx.author.id,
        )
        self.cog.games[guild_id] = game
        self.stop()

        game_view = TicTacToeView(self.cog, game)
        embed = self.cog.create_ttt_embed(game)
        await interaction.response.edit_message(content=None, embed=embed, view=game_view)


# =================================================================
# BLACKJACK
# =================================================================

SUITS = ["♠️", "♥️", "♦️", "♣️"]
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]


def card_value(cards):
    total, aces = 0, 0
    for card in cards:
        rank = card[:-2]
        if rank in ("J", "Q", "K"):
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
    return "  ".join(f"`{c}`" for c in cards)


class BlackjackView(discord.ui.View):

    def __init__(self, cog, ctx, bet, player_cards, dealer_cards):
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
                "❌ Αυτό το Blackjack δεν είναι δικό σου.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Hit", emoji="🎴", style=discord.ButtonStyle.primary)
    async def hit(self, interaction, button):
        self.player_cards.append(self.cog.draw_card())
        value = card_value(self.player_cards)

        if value > 21:
            return await self.finish(interaction, "LOSE")
        if value == 21:
            return await self.stand(interaction, button)

        await interaction.response.edit_message(embed=self.cog.create_bj_embed(self), view=self)

    @discord.ui.button(label="Stand", emoji="🛑", style=discord.ButtonStyle.success)
    async def stand(self, interaction, button):
        while card_value(self.dealer_cards) < 17:
            self.dealer_cards.append(self.cog.draw_card())

        player = card_value(self.player_cards)
        dealer = card_value(self.dealer_cards)

        if dealer > 21 or player > dealer:
            result = "WIN"
        elif player == dealer:
            result = "PUSH"
        else:
            result = "LOSE"

        await self.finish(interaction, result)

    async def finish(self, interaction, result):
        if self.finished:
            return
        self.finished = True
        for child in self.children:
            child.disabled = True

        guild_id = self.ctx.guild.id
        color = discord.Color.green()

        if result == "BLACKJACK":
            payout = int(self.bet * 2.5)
            await economy_service.add_coins(guild_id, self.ctx.author.id, payout, "BLACKJACK_WIN")
            message = f"🃏 **BLACKJACK!**\n💰 Payout: **{payout:,} coins**"
        elif result == "WIN":
            payout = self.bet * 2
            await economy_service.add_coins(guild_id, self.ctx.author.id, payout, "BLACKJACK_WIN")
            message = f"🏆 **YOU WIN!**\n💰 Payout: **{payout:,} coins**"
        elif result == "PUSH":
            await economy_service.add_coins(guild_id, self.ctx.author.id, self.bet, "BLACKJACK_PUSH")
            color = discord.Color.light_grey()
            message = f"🤝 **PUSH**\n💰 Returned: **{self.bet:,} coins**"
        else:
            color = discord.Color.red()
            message = f"💀 **DEALER WINS**\n💸 Lost: **{self.bet:,} coins**"

        embed = self.cog.create_bj_embed(self, reveal=True)
        embed.title = "🏁 BLACKJACK • FINISHED"
        embed.color = color
        embed.add_field(name="Result", value=message, inline=False)

        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    async def on_timeout(self):
        if self.finished:
            return
        self.finished = True
        for child in self.children:
            child.disabled = True


# =================================================================
# GAMES COG
# =================================================================

class GamesCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.games = {}  # guild_id -> TTTGame

    # -------------------------------------------------------------
    # TIC-TAC-TOE
    # -------------------------------------------------------------

    def create_ttt_embed(self, game: TTTGame):
        current = game.challenger if game.current_player_id == game.challenger.id else game.opponent

        board = (
            f"{game.board[0]} {game.board[1]} {game.board[2]}\n"
            f"{game.board[3]} {game.board[4]} {game.board[5]}\n"
            f"{game.board[6]} {game.board[7]} {game.board[8]}"
        )

        opponent_label = "🤖 Bot" if game.vs_bot else game.opponent.display_name

        embed = discord.Embed(
            title="🎮 TIC-TAC-TOE",
            description=(
                f"```text\n{board}\n```\n"
                f"❌ {game.challenger.display_name}\n"
                f"⭕ {opponent_label}\n\n"
                f"💰 **Pot:** {game.wager * 2:,} coins\n\n"
                f"👉 **Σειρά:** {current.mention if hasattr(current, 'mention') else opponent_label}"
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="Viper Project • Make your move")
        return embed

    async def finish_ttt(self, interaction, game: TTTGame, result, view, use_followup=False):
        self.games.pop(game.guild_id, None)

        if result == "DRAW":
            if game.wager > 0:
                await economy_service.add_coins(game.guild_id, game.challenger.id, game.wager, "TTT_DRAW_REFUND")
                if not game.vs_bot:
                    await economy_service.add_coins(game.guild_id, game.opponent.id, game.wager, "TTT_DRAW_REFUND")
            text = "🤝 **DRAW!**\nΤα wagers επιστράφηκαν."
        else:
            winner = game.challenger if result == "❌" else game.opponent
            prize = game.wager * 2

            if prize > 0 and hasattr(winner, "mention"):
                await economy_service.add_coins(game.guild_id, winner.id, prize, "TTT_WIN")

            winner_label = winner.mention if hasattr(winner, "mention") else "🤖 Bot"
            text = f"🏆 **Νικητής:** {winner_label}\n💰 **Prize:** {prize:,} coins"

        embed = self.create_ttt_embed(game)
        embed.title = "🏁 TIC-TAC-TOE • FINISHED"
        embed.add_field(name="Result", value=text, inline=False)

        if use_followup:
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=None)
        else:
            await interaction.response.edit_message(embed=embed, view=None)

    @commands.command(name="ttt", aliases=["tictactoe"])
    async def ttt(self, ctx, opponent: discord.Member = None, wager: int = 0):
        """
        Play Tic-Tac-Toe — vs another player or vs the bot.

        Usage:
            !ttt              -> choose to play vs Bot
            !ttt @user        -> challenge a player
            !ttt @user 100    -> challenge a player with a wager
        """

        if ctx.guild is None:
            return await ctx.send("❌ Το παιχνίδι είναι διαθέσιμο μόνο σε server.")

        if ctx.guild.id in self.games:
            return await ctx.send("❌ Υπάρχει ήδη ενεργή παρτίδα σε αυτόν τον server.")

        # No opponent named -> offer vs Bot
        if opponent is None:
            embed = discord.Embed(
                title="🎮 TIC-TAC-TOE",
                description=(
                    "**Πώς να παίξεις**\n\n"
                    "🤖 Πάτα το κουμπί για να παίξεις εναντίον του bot\n"
                    "👥 Ή γράψε `!ttt @user` για να προκαλέσεις κάποιον\n"
                    "💰 Ή `!ttt @user 100` για να ποντάρεις"
                ),
                color=discord.Color.blurple(),
            )
            view = TTTStartView(self, ctx)
            return await ctx.send(embed=embed, view=view)

        if opponent.bot:
            return await ctx.send("❌ Δεν μπορείς να προκαλέσεις άλλο bot — χρησιμοποίησε `!ttt` για να παίξεις με εμένα.")

        if opponent.id == ctx.author.id:
            return await ctx.send("❌ Δεν μπορείς να παίξεις εναντίον του εαυτού σου.")

        if wager < 0:
            return await ctx.send("❌ Το wager δεν μπορεί να είναι αρνητικό.")

        if wager > 0:
            balance = await economy_service.get_balance(ctx.guild.id, ctx.author.id)
            if balance < wager:
                return await ctx.send(f"❌ Δεν έχεις αρκετά coins.\n💰 Υπόλοιπο: **{balance:,}**")

        embed = discord.Embed(
            title="🎮 TIC-TAC-TOE",
            description=(
                f"### ⚔️ Challenge\n\n"
                f"{ctx.author.mention} **vs** {opponent.mention}\n\n"
                f"💰 Wager: **{wager:,} coins**\n"
                f"🏆 Pot: **{wager * 2:,} coins**\n\n"
                f"{opponent.mention}, θέλεις να παίξεις;"
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="Viper Project • Tic-Tac-Toe")

        view = ChallengeView(self, ctx, opponent, wager)
        await ctx.send(embed=embed, view=view)

    # -------------------------------------------------------------
    # BLACKJACK
    # -------------------------------------------------------------

    def draw_card(self):
        return random.choice(RANKS) + random.choice(SUITS)

    def create_bj_embed(self, view, reveal=False):
        player_value = card_value(view.player_cards)

        if reveal:
            dealer_text = format_cards(view.dealer_cards)
            dealer_value = str(card_value(view.dealer_cards))
        else:
            dealer_text = f"`{view.dealer_cards[0]}`  🂠"
            dealer_value = "?"

        player_bar = "🟩" * min(player_value, 21) // 3 if False else ""  # unused, kept simple below

        embed = discord.Embed(
            title="🃏 ✨ B L A C K J A C K ✨",
            description=(
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎩 **Dealer**\n{dealer_text}\n"
                f"➜ Value: **{dealer_value}**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **{view.ctx.author.display_name}**\n{format_cards(view.player_cards)}\n"
                f"➜ Value: **{player_value}**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 **Bet:** {view.bet:,} coins"
            ),
            color=discord.Color.gold(),
        )
        embed.set_thumbnail(url=view.ctx.author.display_avatar.url)
        embed.set_footer(text="Viper Project • Blackjack  •  Hit or Stand?")
        return embed

    @commands.command(name="bj", aliases=["blackjack"])
    async def blackjack(self, ctx, bet: int = None):
        """
        Play Blackjack.

        Usage:
            !bj 100
        """

        if ctx.guild is None:
            return await ctx.send("❌ Τα games είναι διαθέσιμα μόνο μέσα σε server.")

        if bet is None:
            return await ctx.send(
                "🃏 **BLACKJACK**\n\n"
                "Χρήση: `!bj <bet>`\n\n"
                f"💰 Min bet: **{settings.BJ_MIN_BET:,}**\n"
                f"💰 Max bet: **{settings.BJ_MAX_BET:,}**"
            )

        if bet < settings.BJ_MIN_BET:
            return await ctx.send(f"❌ Το minimum bet είναι **{settings.BJ_MIN_BET:,} coins**.")
        if bet > settings.BJ_MAX_BET:
            return await ctx.send(f"❌ Το maximum bet είναι **{settings.BJ_MAX_BET:,} coins**.")

        success = await economy_service.spend_coins(ctx.guild.id, ctx.author.id, bet, "BLACKJACK_BET")
        if not success:
            balance = await economy_service.get_balance(ctx.guild.id, ctx.author.id)
            return await ctx.send(
                f"❌ **Insufficient funds.**\n💰 Balance: **{balance:,}**\n🎲 Bet: **{bet:,}**"
            )

        player_cards = [self.draw_card(), self.draw_card()]
        dealer_cards = [self.draw_card(), self.draw_card()]

        view = BlackjackView(self, ctx, bet, player_cards, dealer_cards)

        if card_value(player_cards) == 21:
            message = await ctx.send(embed=self.create_bj_embed(view, reveal=True))
            payout = int(bet * 2.5)
            await economy_service.add_coins(ctx.guild.id, ctx.author.id, payout, "BLACKJACK_WIN")

            embed = self.create_bj_embed(view, reveal=True)
            embed.title = "🏁 BLACKJACK • FINISHED"
            embed.color = discord.Color.green()
            embed.add_field(
                name="Result",
                value=f"🃏 **BLACKJACK!**\n💰 Payout: **{payout:,} coins**",
                inline=False,
            )
            await message.edit(embed=embed)
            return

        await ctx.send(embed=self.create_bj_embed(view), view=view)

    # -------------------------------------------------------------
    # SPIN
    # -------------------------------------------------------------

    SPIN_TABLE = [
        (0.20, 0, "💀 Nothing", "Red"),
        (0.35, 0.5, "😬 Small loss", "Red"),
        (0.20, 1, "🤝 Break even", "White"),
        (0.15, 2, "🎉 Nice win", "Green"),
        (0.07, 5, "🔥 Big win", "Yellow"),
        (0.03, 10, "💎 JACKPOT", "Gold"),
    ]

    def get_spin_result(self):
        roll = random.random()
        cumulative = 0.0
        for weight, mult, label, color_name in self.SPIN_TABLE:
            cumulative += weight
            if roll <= cumulative:
                return mult, label, color_name
        return 0, "💀 Nothing", "Red"

    @commands.command(name="spin", aliases=["slots"])
    async def spin(self, ctx, bet: int = None):
        """
        Spin the wheel.

        Usage:
            !spin 100
        """

        if ctx.guild is None:
            return await ctx.send("❌ Το game είναι διαθέσιμο μόνο μέσα σε server.")

        if bet is None:
            embed = discord.Embed(
                title="🎰 ✨ V I P E R   S P I N ✨",
                description=(
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "**Slot Machine**\n\n"
                    "Χρήση: `!spin <bet>`\n\n"
                    f"💰 Min bet: **{settings.SPIN_MIN_BET:,}**\n"
                    f"💰 Max bet: **{settings.SPIN_MAX_BET:,}**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━"
                ),
                color=discord.Color.purple(),
            )
            return await ctx.send(embed=embed)

        if bet < settings.SPIN_MIN_BET:
            return await ctx.send(f"❌ Το minimum bet είναι **{settings.SPIN_MIN_BET:,} coins**.")
        if bet > settings.SPIN_MAX_BET:
            return await ctx.send(f"❌ Το maximum bet είναι **{settings.SPIN_MAX_BET:,} coins**.")

        success = await economy_service.spend_coins(ctx.guild.id, ctx.author.id, bet, "GAME_BET_SPIN")
        if not success:
            balance = await economy_service.get_balance(ctx.guild.id, ctx.author.id)
            return await ctx.send(
                f"❌ **Insufficient funds.**\n💰 Balance: **{balance:,}**\n🎰 Bet: **{bet:,}**"
            )

        try:
            result_mult, label, color_name = self.get_spin_result()
            win_amount = int(bet * result_mult)

            if win_amount > 0:
                await economy_service.add_coins(ctx.guild.id, ctx.author.id, win_amount, "GAME_WIN_SPIN")

            color_map = {
                "Gold": discord.Color.gold(),
                "Yellow": discord.Color.yellow(),
                "Green": discord.Color.green(),
                "White": discord.Color.light_gray(),
                "Red": discord.Color.red(),
            }
            color = color_map.get(color_name, discord.Color.purple())

            reels = [random.choice(["🍒", "🍋", "🔔", "⭐", "7️⃣", "💎"]) for _ in range(3)]
            reel_line = "  ".join(reels)

            if result_mult >= 10:
                title = "💎 JACKPOT!"
            elif result_mult > 1:
                title = "🔥 BIG WIN!"
            elif result_mult == 1:
                title = "🤝 BREAK EVEN"
            elif result_mult > 0:
                title = "🎉 SMALL WIN"
            else:
                title = "💀 NO WIN"

            net = win_amount - bet
            net_line = f"+{net:,}" if net >= 0 else f"{net:,}"

            embed = discord.Embed(
                title=f"🎰 {title}",
                description=(
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"### {reel_line}\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"✨ **{label}**\n\n"
                    f"🎯 Multiplier: **x{result_mult}**\n"
                    f"💰 Bet: **{bet:,} coins**\n"
                    f"💵 Payout: **{win_amount:,} coins**\n"
                    f"📊 Net: **{net_line} coins**"
                ),
                color=color,
            )
            embed.set_thumbnail(url=ctx.author.display_avatar.url)
            embed.set_footer(text="Viper Project • Spin the wheel")

            await ctx.send(embed=embed)

        except Exception as e:
            await economy_service.add_coins(ctx.guild.id, ctx.author.id, bet, "GAME_REFUND_SPIN")
            print(f"[SPIN ERROR] {type(e).__name__}: {e}")
            await ctx.send("❌ Παρουσιάστηκε πρόβλημα στο Spin.\nΤο bet σου επιστράφηκε.")


async def setup(bot):
    await bot.add_cog(GamesCog(bot))