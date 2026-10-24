import os
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

class ConfigError(Exception):
    pass

# ۱. توکن و شناسه گروه
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
GROUP_ID: int = int(os.getenv("GROUP_ID", os.getenv("GROUP_CHAT_ID", "0")))
GROUP_CHAT_ID: int = GROUP_ID

# ۲. شناسه ادمین‌ها
_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: List[int] = [
    int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip().isdigit()
]

# ۳. متغیرهای تاپیک‌ها
TOPIC_1: int = int(os.getenv("TOPIC_1", os.getenv("TOPIC_GENERAL", "1")))
TOPIC_2: int = int(os.getenv("TOPIC_2", os.getenv("TOPIC_PODCAST", "213")))
TOPIC_3: int = int(os.getenv("TOPIC_3", os.getenv("TOPIC_RULES", "14")))
TOPIC_4: int = int(os.getenv("TOPIC_4", os.getenv("TOPIC_PORTFOLIO", "3")))
TOPIC_5: int = int(os.getenv("TOPIC_5", os.getenv("TOPIC_INTRO", "66")))
TOPIC_6: int = int(os.getenv("TOPIC_6", os.getenv("TOPIC_TARIFF", "72")))
TOPIC_7: int = int(os.getenv("TOPIC_7", os.getenv("TOPIC_PROJECTS", "4")))
TOPIC_8: int = int(os.getenv("TOPIC_8", os.getenv("TOPIC_REVIEWS", "473")))
TOPIC_9: int = int(os.getenv("TOPIC_9", os.getenv("TOPIC_AUDIO", "488")))

# نام‌های مستعار تاپیک‌ها
TOPIC_GENERAL = TOPIC_1
TOPIC_PODCAST = TOPIC_2
TOPIC_RULES = TOPIC_3
TOPIC_PORTFOLIO = TOPIC_4
TOPIC_INTRO = TOPIC_5
TOPIC_TARIFF = TOPIC_6
TOPIC_PROJECTS = TOPIC_7
TOPIC_REVIEWS = TOPIC_8
TOPIC_AUDIO = TOPIC_9

# ۴. متغیرهای اخطار، مسدودسازی و نرخ ارسال پیام
MAX_WARNINGS: int = int(os.getenv("MAX_WARNINGS", "3"))
MUTE_DURATION_HOURS: int = int(os.getenv("MUTE_DURATION_HOURS", "24"))
BAN_DURATION_DAYS: int = int(os.getenv("BAN_DURATION_DAYS", "7"))
WARNING_RESET_DAYS: int = int(os.getenv("WARNING_RESET_DAYS", "30"))

GENERAL_HOURLY_LIMIT: int = int(os.getenv("RATE_LIMIT_GENERAL_PER_HOUR", os.getenv("GENERAL_HOURLY_LIMIT", "10")))
GENERAL_DAILY_LIMIT: int = int(os.getenv("GENERAL_DAILY_LIMIT", "15"))
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "bot_database.db")

# دیکشنری تاپیک‌ها
TOPICS: Dict[str, int] = {
    "general": TOPIC_1,
    "podcast": TOPIC_2,
    "rules": TOPIC_3,
    "portfolio": TOPIC_4,
    "intro": TOPIC_5,
    "tariff": TOPIC_6,
    "projects": TOPIC_7,
    "reviews": TOPIC_8,
    "audio": TOPIC_9,
}

class Config:
    def __init__(self):
        self.BOT_TOKEN = BOT_TOKEN
        self.GROUP_ID = GROUP_ID
        self.GROUP_CHAT_ID = GROUP_CHAT_ID
        self.ADMIN_IDS = ADMIN_IDS
        self.TOPIC_1 = TOPIC_1
        self.TOPIC_2 = TOPIC_2
        self.TOPIC_3 = TOPIC_3
        self.TOPIC_4 = TOPIC_4
        self.TOPIC_5 = TOPIC_5
        self.TOPIC_6 = TOPIC_6
        self.TOPIC_7 = TOPIC_7
        self.TOPIC_8 = TOPIC_8
        self.TOPIC_9 = TOPIC_9
        self.TOPIC_GENERAL = TOPIC_GENERAL
        self.TOPIC_PODCAST = TOPIC_PODCAST
        self.TOPIC_RULES = TOPIC_RULES
        self.TOPIC_PORTFOLIO = TOPIC_PORTFOLIO
        self.TOPIC_INTRO = TOPIC_INTRO
        self.TOPIC_TARIFF = TOPIC_TARIFF
        self.TOPIC_PROJECTS = TOPIC_PROJECTS
        self.TOPIC_REVIEWS = TOPIC_REVIEWS
        self.TOPIC_AUDIO = TOPIC_AUDIO
        self.MAX_WARNINGS = MAX_WARNINGS
        self.MUTE_DURATION_HOURS = MUTE_DURATION_HOURS
        self.BAN_DURATION_DAYS = BAN_DURATION_DAYS
        self.WARNING_RESET_DAYS = WARNING_RESET_DAYS
        self.GENERAL_HOURLY_LIMIT = GENERAL_HOURLY_LIMIT
        self.GENERAL_DAILY_LIMIT = GENERAL_DAILY_LIMIT
        self.DATABASE_PATH = DATABASE_PATH
        self.TOPICS = TOPICS

_config_instance = Config()

def load_config() -> Config:
    return _config_instance

config = _config_instance
