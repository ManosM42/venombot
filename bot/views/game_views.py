import discord
from bot.services.game_service import game_service
from bot.services.economy_service import economy_service

class BJView(discord.ui.View):
    def __init__(self, guild_id, user_id, bet, session_id):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.user_id = user_id
        self.bet = bet
        self.session_id = session_id
        self.user_hand = [game_service.deal_card(), game_service.deal_card()]
        self.bot_hand = [game_service.deal_card(), game_service.deal_card()]
        self.game_over = False

    def get_embed(self):
        user_score = game_service.calculate_bj_score(self.user_hand)
        bot_score = game_service.calculate_bj_score(self.bot_hand)

        embed = discord.Embed(title="🃏 BLACKJACK", color=discord.Color.blue())
        embed.add_field(name="Your Hand", value=f"{' '.join(map(str, self.user_hand))}\nValue: {user_score}", inline=False)
        embed.add_field(name="Dealer Hand", value=f"{self.bot_hand[0]} ??", inline=False)
        return embed

    async def end_game(self, interaction, result_text, win=False, payout=0):
        self.game_over = True
        if win:
            await economy_service.reward_winner(self.guild_id, self.user_id, payout, "BLACKJACK", self.session_id)

        embed = self.get_embed()
        embed.description = f"**{result_text}**"
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.defer()

        self.user_hand.append(game_service.deal_card())
        score = game_service.calculate_bj_score(self.user_hand)

        if score > 21:
            await self.end_game(interaction, f"💀 BUST! You lost {self.bet} coins.", win=False)
        else:
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.defer()

        user_score = game_service.calculate_bj_score(self.user_hand)
        bot_score = game_service.calculate_bj_score(self.bot_hand)

        while bot_score < 17:
            self.bot_hand.append(game_service.deal_card())
            bot_score = game_service.calculate_bj_score(self.bot_hand)

        if bot_score > 21 or user_score > bot_score:
            await self.end_game(interaction, f"🏆 YOU WIN! You won {self.bet * 2} coins.", win=True, payout=self.bet)
        elif user_score < bot_score:
            await self.end_game(interaction, f"💀 DEALER WINS! You lost {self.bet} coins.", win=False)
        else:
            await self.end_game(interaction, "🤝 PUSH! Your bet is returned.", win=True, payout=self.bet)

class TTTView(discord.ui.View):
    def __init__(self, guild_id, user1, user2, bet=0, session_id=None):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.user1 = user1
        self.user2 = user2
        self.bet = bet
        self.session_id = session_id
        self.current_turn = user1
        self.board = ["⬜" for _ in range(9)]

    def check_winner(self):
        wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
        for a,b,c in wins:
            if self.board[a] == self.board[b] == self.board[c] != "⬜":
                return self.board[a]
        if "⬜" not in self.board: return "Tie"
        return None

    def get_embed(self):
        b = self.board
        board_str = (
            f"{b[0]} {b[1]} {b[2]}\n"
            f"{b[3]} {b[4]} {b[5]}\n"
            f"{b[6]} {b[7]} {b[8]}"
        )
        embed = discord.Embed(title=" Tic-Tac-Toe", description=f"```\n{board_str}\n```", color=discord.Color.blue())
        embed.set_footer(text=f"Turn: {self.current_turn.mention}")
        return embed

    async def handle_click(self, interaction, idx):
        if interaction.user != self.current_turn:
            return await interaction.response.send_message("Not your turn!", ephemeral=True)
        if self.board[idx] != "⬜":
            return await interaction.response.send_message("Taken!", ephemeral=True)

        symbol = "❌" if self.current_turn == self.user1 else "⭕"
        self.board[idx] = symbol

        winner = self.check_winner()
        if winner:
            if winner == "Tie":
                res = "It's a Draw!"
                if self.bet > 0:
                    await economy_service.reward_winner(self.guild_id, self.user1.id, self.bet, "TTT_REFUND", self.session_id)
                    await economy_service.reward_winner(self.guild_id, self.user2.id, self.bet, "TTT_REFUND", self.session_id)
            else:
                winner_user = self.user1 if symbol == "❌" else self.user2
                res = f"Winner: {winner_user.mention}!"
                if self.bet > 0:
                    await economy_service.reward_winner(self.guild_id, winner_user.id, self.bet * 2, "TTT_WIN", self.session_id)

            await interaction.response.edit_message(embed=self.get_embed(), content=res, view=None)
            self.stop()
            return

        self.current_turn = self.user2 if self.current_turn == self.user1 else self.user1
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    # We'll use a loop to add buttons 0-8
    async def setup_buttons(self):
        for i in range(9):
            btn = discord.ui.Button(label=str(i), style=discord.ButtonStyle.secondary)
            btn.callback = self.make_callback(i)
            self.add_item(btn)

    def make_callback(self, idx):
        async def callback(interaction):
            await self.handle_click(interaction, idx)
        return callback
