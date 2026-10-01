
import discord
from discord.ext import commands
from dataclasses import dataclass

from bot.services.economy_service import economy_service


@dataclass
class TTTGame:
    guild_id: int
    challenger: discord.Member
    opponent: discord.Member
    wager: int

    board: list
    current_player_id: int

    message: discord.Message | None = None
    finished: bool = False


class TicTacToeView(discord.ui.View):

    def __init__(self, cog, game: TTTGame):
        super().__init__(timeout=180)

        self.cog = cog
        self.game = game

        for index in range(9):

            button = discord.ui.Button(
                label=" ",
                emoji="⬜",
                style=discord.ButtonStyle.secondary,
                row=index // 3
            )

            button.callback = self.create_callback(index)

            self.add_item(button)

    def create_callback(self, index):

        async def callback(interaction: discord.Interaction):

            game = self.game

            # Only the two players can interact
            if interaction.user.id not in (
                game.challenger.id,
                game.opponent.id
            ):
                await interaction.response.send_message(
                    "❌ Δεν συμμετέχεις σε αυτή την παρτίδα.",
                    ephemeral=True
                )
                return

            # Check turn
            if interaction.user.id != game.current_player_id:

                await interaction.response.send_message(
                    "⏳ Δεν είναι η σειρά σου.",
                    ephemeral=True
                )

                return

            # Check occupied cell
            if game.board[index] != "⬜":

                await interaction.response.send_message(
                    "❌ Αυτή η θέση είναι ήδη πιασμένη.",
                    ephemeral=True
                )

                return

            # Determine symbol
            if interaction.user.id == game.challenger.id:
                symbol = "❌"
            else:
                symbol = "⭕"

            game.board[index] = symbol

            # Update button
            button = self.children[index]

            button.emoji = symbol
            button.label = " "
            button.disabled = True

            # Check winner
            result = self.check_winner(game.board)

            if result:

                game.finished = True

                await self.cog.finish_game(
                    interaction,
                    game,
                    result
                )

                self.stop()
                return

            # Switch player
            if interaction.user.id == game.challenger.id:
                game.current_player_id = game.opponent.id
            else:
                game.current_player_id = game.challenger.id

            embed = self.cog.create_embed(game)

            await interaction.response.edit_message(
                embed=embed,
                view=self
            )

        return callback

    @staticmethod
    def check_winner(board):

        combinations = [

            (0, 1, 2),
            (3, 4, 5),
            (6, 7, 8),

            (0, 3, 6),
            (1, 4, 7),
            (2, 5, 8),

            (0, 4, 8),
            (2, 4, 6)

        ]

        for a, b, c in combinations:

            if (
                board[a] != "⬜"
                and
                board[a] == board[b] == board[c]
            ):

                return board[a]

        if "⬜" not in board:
            return "DRAW"

        return None

    async def on_timeout(self):

        if self.game.finished:
            return

        self.game.finished = True

        for child in self.children:
            child.disabled = True

        # Refund wager on timeout
        if self.game.wager > 0:

            await economy_service.add_coins(
                self.game.guild_id,
                self.game.challenger.id,
                self.game.wager,
                "TTT_TIMEOUT_REFUND"
            )

            await economy_service.add_coins(
                self.game.guild_id,
                self.game.opponent.id,
                self.game.wager,
                "TTT_TIMEOUT_REFUND"
            )


class ChallengeView(discord.ui.View):

    def __init__(self, cog, ctx, opponent, wager):

        super().__init__(timeout=60)

        self.cog = cog
        self.ctx = ctx
        self.opponent = opponent
        self.wager = wager
        self.accepted = False

    @discord.ui.button(
        label="Accept",
        emoji="✅",
        style=discord.ButtonStyle.success
    )
    async def accept(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.user.id != self.opponent.id:

            await interaction.response.send_message(
                "❌ Μόνο ο αντίπαλος μπορεί να αποδεχτεί.",
                ephemeral=True
            )

            return

        guild_id = self.ctx.guild.id

        # Check opponent balance
        if self.wager > 0:

            opponent_balance = await economy_service.get_balance(
                guild_id,
                self.opponent.id
            )

            if opponent_balance < self.wager:

                await interaction.response.send_message(
                    f"❌ Δεν έχεις αρκετά coins. "
                    f"Υπόλοιπο: **{opponent_balance:,}**.",
                    ephemeral=True
                )

                return

            # Remove challenger wager
            challenger_paid = await economy_service.spend_coins(
                guild_id,
                self.ctx.author.id,
                self.wager,
                "TTT_WAGER"
            )

            if not challenger_paid:

                await interaction.response.send_message(
                    "❌ Το ποντάρισμα του challenger δεν είναι πλέον διαθέσιμο.",
                    ephemeral=True
                )

                return

            # Remove opponent wager
            opponent_paid = await economy_service.spend_coins(
                guild_id,
                self.opponent.id,
                self.wager,
                "TTT_WAGER"
            )

            if not opponent_paid:

                await economy_service.add_coins(
                    guild_id,
                    self.ctx.author.id,
                    self.wager,
                    "TTT_REFUND"
                )

                await interaction.response.send_message(
                    "❌ Δεν μπόρεσα να κλειδώσω το δεύτερο ποντάρισμα.",
                    ephemeral=True
                )

                return

        game = TTTGame(
            guild_id=guild_id,
            challenger=self.ctx.author,
            opponent=self.opponent,
            wager=self.wager,
            board=["⬜"] * 9,
            current_player_id=self.ctx.author.id
        )

        self.cog.games[guild_id] = game

        self.stop()

        game_view = TicTacToeView(
            self.cog,
            game
        )

        embed = self.cog.create_embed(game)

        await interaction.response.edit_message(
            content=None,
            embed=embed,
            view=game_view
        )

    @discord.ui.button(
        label="Decline",
        emoji="❌",
        style=discord.ButtonStyle.danger
    )
    async def decline(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.user.id != self.opponent.id:

            await interaction.response.send_message(
                "❌ Μόνο ο αντίπαλος μπορεί να απαντήσει.",
                ephemeral=True
            )

            return

        self.stop()

        await interaction.response.edit_message(
            content="❌ Η πρόκληση απορρίφθηκε.",
            embed=None,
            view=None
        )


class TicTacToe(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        self.games = {}

    @commands.command(
        name="ttt",
        aliases=["tictactoe"]
    )
    async def ttt(
        self,
        ctx,
        opponent: discord.Member = None,
        wager: int = 0
    ):

        if ctx.guild is None:

            await ctx.send(
                "❌ Το παιχνίδι είναι διαθέσιμο μόνο σε server."
            )

            return

        if opponent is None:

            await ctx.send(
                "🎮 **TIC-TAC-TOE**\n\n"
                "Χρήση:\n"
                "`!ttt @user`\n"
                "`!ttt @user 100`"
            )

            return

        if opponent.bot:

            await ctx.send(
                "❌ Δεν μπορείς να παίξεις με bot."
            )

            return

        if opponent.id == ctx.author.id:

            await ctx.send(
                "❌ Δεν μπορείς να παίξεις εναντίον του εαυτού σου."
            )

            return

        if wager < 0:

            await ctx.send(
                "❌ Το wager δεν μπορεί να είναι αρνητικό."
            )

            return

        if ctx.guild.id in self.games:

            await ctx.send(
                "❌ Υπάρχει ήδη ενεργή παρτίδα σε αυτόν τον server."
            )

            return

        if wager > 0:

            balance = await economy_service.get_balance(
                ctx.guild.id,
                ctx.author.id
            )

            if balance < wager:

                await ctx.send(
                    f"❌ Δεν έχεις αρκετά coins.\n"
                    f"💰 Υπόλοιπο: **{balance:,}**"
                )

                return

        embed = discord.Embed(
            title="🎮 TIC-TAC-TOE",
            description=(
                f"### ⚔️ Challenge\n\n"
                f"{ctx.author.mention} **vs** {opponent.mention}\n\n"
                f"💰 Wager: **{wager:,} coins**\n"
                f"🏆 Pot: **{wager * 2:,} coins**\n\n"
                f"{opponent.mention}, θέλεις να παίξεις;"
            ),
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text="Viper Project • Tic-Tac-Toe"
        )

        view = ChallengeView(
            self,
            ctx,
            opponent,
            wager
        )

        await ctx.send(
            embed=embed,
            view=view
        )

    def create_embed(self, game):

        if game.current_player_id == game.challenger.id:
            current = game.challenger
        else:
            current = game.opponent

        board = (
            f"{game.board[0]} {game.board[1]} {game.board[2]}\n"
            f"{game.board[3]} {game.board[4]} {game.board[5]}\n"
            f"{game.board[6]} {game.board[7]} {game.board[8]}"
        )

        embed = discord.Embed(
            title="🎮 TIC-TAC-TOE",
            description=(
                f"```text\n"
                f"{board}\n"
                f"```\n"
                f"❌ {game.challenger.display_name}\n"
                f"⭕ {game.opponent.display_name}\n\n"
                f"💰 **Pot:** {game.wager * 2:,} coins\n\n"
                f"👉 **Σειρά:** {current.mention}"
            ),
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text="Viper Project • Make your move"
        )

        return embed

    async def finish_game(
        self,
        interaction,
        game,
        result
    ):

        self.games.pop(game.guild_id, None)

        if result == "DRAW":

            if game.wager > 0:

                await economy_service.add_coins(
                    game.guild_id,
                    game.challenger.id,
                    game.wager,
                    "TTT_DRAW_REFUND"
                )

                await economy_service.add_coins(
                    game.guild_id,
                    game.opponent.id,
                    game.wager,
                    "TTT_DRAW_REFUND"
                )

            text = (
                "🤝 **DRAW!**\n"
                "Τα wagers επιστράφηκαν."
            )

        else:

            if result == "❌":
                winner = game.challenger
            else:
                winner = game.opponent

            prize = game.wager * 2

            if prize > 0:

                await economy_service.add_coins(
                    game.guild_id,
                    winner.id,
                    prize,
                    "TTT_WIN"
                )

            text = (
                f"🏆 **Νικητής:** {winner.mention}\n"
                f"💰 **Prize:** {prize:,} coins"
            )

        embed = self.create_embed(game)

        embed.title = "🏁 TIC-TAC-TOE • FINISHED"

        embed.add_field(
            name="Result",
            value=text,
            inline=False
        )

        await interaction.response.edit_message(
            embed=embed,
            view=None
        )


async def setup(bot):

    await bot.add_cog(
        TicTacToe(bot)
    )

