import os
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()

@dataclass
class Settings:
    # Bot Basics
    TOKEN: str = os.getenv("DISCORD_TOKEN", "")
    PREFIX: str = os.getenv("PREFIX", "!")

    # Role & Channel IDs
    LOG_CHANNEL_ID: int = int(os.getenv("LOG_CHANNEL_ID", 0))
    STAFF_ROLE_ID: int = int(os.getenv("STAFF_ROLE_ID", 0))
    TICKET_CATEGORY_ID: int = int(os.getenv("TICKET_CATEGORY_ID", 0))
    APPLICATION_REVIEW_CHANNEL_ID: int = int(os.getenv("APPLICATION_REVIEW_CHANNEL_ID", 0))

    # Economy Settings
    STARTING_BALANCE: int = 500
    DAILY_REWARD: int = 250

    # Game Settings - Blackjack
    BJ_MIN_BET: int = 10
    BJ_MAX_BET: int = 10000
    BJ_WIN_MULTIPLIER: float = 2.0
    BJ_BLACKJACK_MULTIPLIER: float = 2.5

    # Game Settings - Spin
    SPIN_MIN_BET: int = 10
    SPIN_MAX_BET: int = 5000
    SPIN_REWARDS: dict = None # To be defined in service

    # Game Settings - Tic Tac Toe
    TTT_MIN_BET: int = 10
    TTT_MAX_BET: int = 10000

settings = Settings()
