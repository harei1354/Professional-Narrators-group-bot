import os
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

class ConfigError(Exception):
    pass

# ۱. مقادیر اصلی
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
GROUP_ID: int = int(os.getenv("GROUP_CHAT_ID", os.getenv("GROUP_ID", "0")))
GROUP_CHAT_ID: int = GROUP_ID

# ۲. ادمین‌ها
_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: List[int] = [
    int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip().isdigit()
]

# ۳. متغیرهای تاپیک‌ها (پشتیبانی همزمان از نام‌های عددی و حروفی)
TOPIC_GENERAL: int = int(os.getenv("TOPIC_GENERAL", os.getenv("TOPIC_1", "1")))
TOPIC_PODCAST: int = int(os.getenv("TOPIC_PODCAST", os.getenv("TOPIC_2", "213")))
TOPIC_RULES: int = int(os.getenv("TOPIC_RULES", os.getenv("TOPIC_3", "14")))
TOPIC_PORTFOLIO: int = int(os.getenv("TOPIC_PORTFOLIO", os.getenv("TOPIC_4", "3")))
TOPIC_INTRO: int = int(os.getenv("TOPIC_INTRO", os.getenv("TOPIC_5", "66")))
TOPIC_TARIFF: int = int(os.getenv("TOPIC_TARIFF", os.getenv("TOPIC_6", "72")))
TOPIC_PROJECTS: int = int(os.getenv("TOPIC_PROJECTS", os.getenv("TOPIC_7", "4")))
TOPIC_REVIEWS: int = int(os.getenv("TOPIC_REVIEWS", os.getenv("TOPIC_8", "473")))
TOPIC_AUDIO: int = int(os.getenv("TOPIC_AUDIO", os.getenv("TOPIC_9", "488")))

# متغیرهای مستعار TOPIC_1 تا TOPIC_9
TOPIC_1 = TOPIC_GENERAL
TOPIC_2 = TOPIC_PODCAST
TOPIC_3 = TOPIC_RULES
TOPIC_4 = TOPIC_PORTFOLIO
TOPIC_5 = TOPIC_INTRO
TOPIC_6 = TOPIC_TARIFF
TOPIC_7 = TOPIC_PROJECTS
TOPIC_8 = TOPIC_REVIEWS
TOPIC_9 = TOPIC_AUDIO

# ۴. محدودیت‌ها
GENERAL_HOURLY_LIMIT: int = int(os.getenv("RATE_LIMIT_GENERAL_PER_HOUR", os.getenv("GENERAL_HOURLY_LIMIT", "10")))
GENERAL_DAILY_LIMIT: int = int(os.getenv("GENERAL_DAILY_LIMIT", "15"))
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "bot_database.db")

TOPICS: Dict[str, int] = {
    "general": TOPIC_GENERAL,
    "podcast": TOPIC_PODCAST,
    "rules": TOPIC_RULES,
    "portfolio": TOPIC_PORTFOLIO,
    "intro": TOPIC_INTRO,
    "tariff": TOPIC_TARIFF,
    "projects": TOPIC_PROJECTS,
    "reviews": TOPIC_REVIEWS,
    "audio": TOPIC_AUDIO,
}

class Config:
    def __init__(self):
        self.BOT_TOKEN = BOT_TOKEN
        self.GROUP_ID = GROUP_ID
        self.GROUP_CHAT_ID = GROUP_CHAT_ID
        self.ADMIN_IDS = ADMIN_IDS
        self.TOPIC_GENERAL = TOPIC_GENERAL
        self.TOPIC_PODCAST = TOPIC_PODCAST
        self.TOPIC_RULES = TOPIC_RULES
        self.TOPIC_PORTFOLIO = TOPIC_PORTFOLIO
        self.TOPIC_INTRO = TOPIC_INTRO
        self.TOPIC_TARIFF = TOPIC_TARIFF
        self.TOPIC_PROJECTS = TOPIC_PROJECTS
        self.TOPIC_REVIEWS = TOPIC_REVIEWS
        self.TOPIC_AUDIO = TOPIC_AUDIO
        self.GENERAL_HOURLY_LIMIT = GENERAL_HOURLY_LIMIT
        self.GENERAL_DAILY_LIMIT = GENERAL_DAILY_LIMIT
        self.DATABASE_PATH = DATABASE_PATH
        self.TOPICS = TOPICS

_config_instance = Config()

def load_config() -> Config:
    return _config_instance

config = _config_instance
