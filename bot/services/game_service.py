import random
import uuid
from bot.database.manager import db
from bot.config.settings import settings

class GameService:
    def __init__(self, economy_service):
        self.economy = economy_service

    async def lock_wager(self, guild_id: int, user_id: int, amount: int) -> bool:
        """Attempts to deduct a bet amount to lock it for a game."""
        return await self.economy.spend_coins(guild_id, user_id, amount, "GAME_BET")

    async def reward_winner(self, guild_id: int, user_id: int, amount: int, game_name: str, session_id: str):
        """Rewards a winner with a specific amount."""
        await self.economy.add_coins(guild_id, user_id, amount, f"GAME_WIN_{game_name}", session_id)

    async def refund_wager(self, guild_id: int, user_id: int, amount: int, session_id: str):
        """Refunds a locked wager."""
        await self.economy.add_coins(guild_id, user_id, amount, "GAME_REFUND", session_id)

    # Blackjack Logic
    def deal_card(self):
        return random.randint(2, 11)

    def calculate_bj_score(self, hand):
        score = sum(hand)
        aces = hand.count(11)
        while score > 21 and aces:
            score -= 10
            aces -= 1
        return score

    # Spin Logic
    def get_spin_result(self):
        # Configuration for spin rewards
        # Weight: (multiplier, label, color)
        rewards = [
            (10, "JACKPOT 💎", "Gold"),
            (5, "BIG WIN 🟡", "Yellow"),
            (2, "WIN 🟢", "Green"),
            (1.25, "SMALL WIN ⚪", "White"),
            (0, "LOSS 🔴", "Red")
        ]
        weights = [1, 5, 14, 30, 50] # Total 100%

        return random.choices(rewards, weights=weights, k=1)[0]

game_service = None # To be initialized in main.py
