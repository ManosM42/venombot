import os
import random
import asyncio
import discord
from discord.ext import commands
from dataclasses import dataclass
from dotenv import load_dotenv

from bot.services.economy_service import economy_service
from bot.config.settings import settings

load_dotenv()


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
# SPIN — Venom Shop reward wheel (no bet, 3h cooldown, opens a ticket on win)
# =================================================================

def _env_int(name: str) -> int:
    try:
        return int(os.getenv(name, "0"))
    except (TypeError, ValueError):
        return 0

SPIN_CATEGORY_ID = _env_int("SPIN_CATEGORY_ID")
LOG_CHANNEL_ID = _env_int("LOG_CHANNEL_ID")
FOUNDER_ROLE_ID = _env_int("FOUNDER_ROLE_ID")
COFOUNDER_ROLE_ID = _env_int("COFOUNDER_ROLE_ID")
STAFF_ROLE_ID = _env_int("STAFF_ROLE_ID")

SPIN_BRAND = "Venom Shop"
SPIN_GLASS = 0x8FD3FF
SPIN_GOLD = 0xFFD37A
SPIN_GREEN = 0x7CFFCB
SPIN_RED = 0xFF8FA3
SPIN_SEP = "▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰"

SPIN_COOLDOWN_SECONDS = 3 * 60 * 60  # 3 hours

# weight = chance in %. "Nothing" silently absorbs whatever % is left over.
SPIN_REWARDS = [
    {"name": "Custom Design",        "emoji": "🎨", "weight": 0.1},
    {"name": "14 Days Free Promo",   "emoji": "🚀", "weight": 0.3},
    {"name": "VIP Role",             "emoji": "⭐", "weight": 0.5},
    {"name": "Free Boosts Reward",   "emoji": "💎", "weight": 1.5},
    {"name": "DM ALL BOT",           "emoji": "📨", "weight": 2.0},
    {"name": "1.000 Coins",          "emoji": "🪙", "weight": 5.0},
    {"name": "500 Coins",            "emoji": "🪙", "weight": 10.0},
]


def _roll_spin_reward():
    total_weighted = sum(r["weight"] for r in SPIN_REWARDS)
    nothing_weight = max(0.0, 100.0 - total_weighted)
    pool = SPIN_REWARDS + [{"name": "Nothing", "emoji": "💨", "weight": nothing_weight}]
    weights = [r["weight"] for r in pool]
    return random.choices(pool, weights=weights, k=1)[0]


def _find_role(guild: discord.Guild, role_id: int, *names: str):
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


def _get_spin_roles(guild: discord.Guild):
    founder = _find_role(guild, FOUNDER_ROLE_ID, "founder")
    cofounder = _find_role(guild, COFOUNDER_ROLE_ID, "co founder", "co-founder", "cofounder")
    staff = _find_role(guild, STAFF_ROLE_ID, "staff team", "staff")
    return founder, cofounder, staff


def _can_close_spin(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    founder, _cofounder, staff = _get_spin_roles(member.guild)
    allowed = {r.id for r in (founder, staff) if r}
    return any(r.id in allowed for r in member.roles)


def _spin_topic_owner_id(channel: discord.TextChannel):
    if channel.topic and channel.topic.startswith("spin-owner:"):
        try:
            return int(channel.topic.split(":")[1].split("|")[0])
        except ValueError:
            return None
    return None


def _safe_name(text: str) -> str:
    cleaned = "".join(c for c in text.lower() if c.isalnum() or c in "-_")
    return cleaned[:30] or "user"


def _format_cooldown(seconds: float) -> str:
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


class SpinControlView(discord.ui.View):
    """Persistent close/cancel buttons for spin-reward tickets."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close", emoji="🔒", style=discord.ButtonStyle.danger,
                       custom_id="venom:spin:close")
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not _can_close_spin(interaction.user):
            return await interaction.response.send_message(
                "❌ Only **Staff** and **Founder** can close this.", ephemeral=True
            )
        try:
            await interaction.response.send_message("🔒 Closing in **5 seconds**...")
        except discord.NotFound:
            return
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Spin ticket closed by {interaction.user}")
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Cancel", emoji="🗑️", style=discord.ButtonStyle.secondary,
                       custom_id="venom:spin:cancel")
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        owner_id = _spin_topic_owner_id(interaction.channel)
        if interaction.user.id != owner_id and not _can_close_spin(interaction.user):
            return await interaction.response.send_message(
                "❌ Only the ticket owner or staff can cancel this.", ephemeral=True
            )
        try:
            await interaction.response.send_message("🗑️ Cancelling in **5 seconds**...")
        except discord.NotFound:
            return
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Spin ticket cancelled by {interaction.user}")
        except discord.HTTPException:
            pass


async def _create_spin_ticket(ctx: commands.Context, reward: dict):
    guild = ctx.guild
    user = ctx.author

    founder, cofounder, staff = _get_spin_roles(guild)

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

    category = guild.get_channel(SPIN_CATEGORY_ID) if SPIN_CATEGORY_ID else None
    if category is not None and not isinstance(category, discord.CategoryChannel):
        category = None

    try:
        channel = await guild.create_text_channel(
            name=f"spin-{_safe_name(user.name)}",
            category=category,
            overwrites=overwrites,
            topic=f"spin-owner:{user.id}",
            reason=f"Spin reward ticket for {user}",
        )
    except discord.HTTPException:
        await ctx.send("❌ I couldn't create the ticket channel. Check my permissions.")
        return None

    embed = discord.Embed(
        title=f"{reward['emoji']}  Spin Reward — Redeem",
        description=f"{SPIN_SEP}\n\nCongratulations {user.mention}! 🎉\n\n{SPIN_SEP}",
        color=SPIN_GOLD,
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="🎁 Reward", value=f"```{reward['name']}```", inline=True)
    embed.add_field(name="👤 Won by", value=user.mention, inline=True)
    embed.set_author(name=f"{SPIN_BRAND} • Spin Redeem")
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text="Staff will verify and process this reward shortly.")

    pings = [user.mention] + [r.mention for r in (founder, staff, cofounder) if r]
    await channel.send(
        content=" ".join(pings),
        embed=embed,
        view=SpinControlView(),
        allowed_mentions=discord.AllowedMentions(users=True, roles=True),
    )
    return channel


async def _animate_spin(ctx: commands.Context):
    frames = ["🎰 | ❔ ❔ ❔", "🎰 | 🍀 ❔ ❔", "🎰 | 🍀 🎲 ❔"]
    embed = discord.Embed(title="🎰  Spinning...", description=frames[0], color=SPIN_GLASS)
    msg = await ctx.send(embed=embed)
    for frame in frames[1:]:
        await asyncio.sleep(0.6)
        embed.description = frame
        try:
            await msg.edit(embed=embed)
        except discord.HTTPException:
            pass
    return msg


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
    # SPIN — reward wheel, 3h cooldown, opens a ticket on any win
    # -------------------------------------------------------------

    @commands.command(name="spin")
    @commands.cooldown(1, SPIN_COOLDOWN_SECONDS, commands.BucketType.user)
    async def spin(self, ctx: commands.Context):
        """
        Spin the Venom Shop reward wheel. One spin every 3 hours.

        Usage:
            !spin
        """

        if ctx.guild is None:
            return await ctx.send("❌ Το spin είναι διαθέσιμο μόνο μέσα σε server.")

        msg = await _animate_spin(ctx)
        reward = _roll_spin_reward()

        await asyncio.sleep(0.4)

        if reward["name"] == "Nothing":
            result = discord.Embed(
                title="🎰  Spin Result",
                description=(f"{SPIN_SEP}\n\n{reward['emoji']} **{reward['name']}**\n\n"
                             "Better luck next time!\n\n"
                             f"Come back in **3 hours**.\n\n{SPIN_SEP}"),
                color=SPIN_RED,
            )
            result.set_footer(text=f"{SPIN_BRAND} • Spin")
            await msg.edit(embed=result)
            return

        result = discord.Embed(
            title="🎉  You Won!",
            description=(f"{SPIN_SEP}\n\n{reward['emoji']} **{reward['name']}**\n\n"
                         "Opening a ticket to redeem your reward...\n\n"
                         f"{SPIN_SEP}"),
            color=SPIN_GREEN,
        )
        result.set_footer(text=f"{SPIN_BRAND} • Spin")
        await msg.edit(embed=result)

        channel = await _create_spin_ticket(ctx, reward)
        if channel:
            go = discord.Embed(description=f"🎫 {channel.mention}", color=SPIN_GREEN)
            await ctx.send(embed=go)

        if LOG_CHANNEL_ID:
            log_channel = ctx.guild.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                log_embed = discord.Embed(
                    title="🎰 Spin Win",
                    description=f"{ctx.author.mention} won **{reward['name']}**",
                    color=SPIN_GOLD,
                )
                try:
                    await log_channel.send(embed=log_embed)
                except discord.HTTPException:
                    pass

    @spin.error
    async def spin_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CommandOnCooldown):
            left = _format_cooldown(error.retry_after)
            embed = discord.Embed(
                title="⏳ Spin on Cooldown",
                description=f"You already spun! Come back in **{left}**.",
                color=SPIN_RED,
            )
            await ctx.send(embed=embed, delete_after=10)


async def setup(bot):
    bot.add_view(SpinControlView())
    await bot.add_cog(GamesCog(bot))