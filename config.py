import os
from typing import Dict, List, Optional
from dotenv import load_dotenv

# بارگذاری متغیرهای محیطی از فایل .env در صورت وجود
load_dotenv()

class ConfigError(Exception):
    """خطای تنظیمات و متغیرهای محیطی"""
    pass

class Config:
    def __init__(self):
        # توکن ربات تلگرام
        self.BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
        if not self.BOT_TOKEN:
            raise ConfigError("متغیر محیطی BOT_TOKEN تنظیم نشده است!")

        # شناسه سوپرگروه
        self.GROUP_CHAT_ID: int = int(os.getenv("GROUP_CHAT_ID", "0"))
        
        # شناسه مدیران (عددی با جداکننده کاما)
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        self.ADMIN_IDS: List[int] = [
            int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()
        ]

        # شناسه‌های تاپیک‌ها
        self.TOPIC_GENERAL: int = int(os.getenv("TOPIC_GENERAL", os.getenv("TOPIC_1", "1")))
        self.TOPIC_PODCAST: int = int(os.getenv("TOPIC_PODCAST", os.getenv("TOPIC_2", "213")))
        self.TOPIC_RULES: int = int(os.getenv("TOPIC_RULES", os.getenv("TOPIC_3", "14")))
        self.TOPIC_PORTFOLIO: int = int(os.getenv("TOPIC_PORTFOLIO", os.getenv("TOPIC_4", "3")))
        self.TOPIC_INTRO: int = int(os.getenv("TOPIC_INTRO", os.getenv("TOPIC_5", "66")))
        self.TOPIC_TARIFF: int = int(os.getenv("TOPIC_TARIFF", os.getenv("TOPIC_6", "72")))
        self.TOPIC_PROJECTS: int = int(os.getenv("TOPIC_PROJECTS", os.getenv("TOPIC_7", "4")))
        self.TOPIC_REVIEWS: int = int(os.getenv("TOPIC_REVIEWS", os.getenv("TOPIC_8", "473")))
        self.TOPIC_AUDIO: int = int(os.getenv("TOPIC_AUDIO", os.getenv("TOPIC_9", "488")))

        # نگاشت تاپیک‌ها
        self.TOPICS: Dict[str, int] = {
            "general": self.TOPIC_GENERAL,
            "podcast": self.TOPIC_PODCAST,
            "rules": self.TOPIC_RULES,
            "portfolio": self.TOPIC_PORTFOLIO,
            "intro": self.TOPIC_INTRO,
            "tariff": self.TOPIC_TARIFF,
            "projects": self.TOPIC_PROJECTS,
            "reviews": self.TOPIC_REVIEWS,
            "audio": self.TOPIC_AUDIO,
        }

        # محدودیت‌های ارسال پیام در گفتگوی عمومی
        self.GENERAL_HOURLY_LIMIT: int = int(os.getenv("RATE_LIMIT_GENERAL_PER_HOUR", os.getenv("GENERAL_HOURLY_LIMIT", "10")))
        self.GENERAL_DAILY_LIMIT: int = int(os.getenv("GENERAL_DAILY_LIMIT", "15"))

        # مسیر فایل دیتابیس
        self.DATABASE_PATH: str = os.getenv("DATABASE_PATH", "bot_database.db")


_config_instance: Optional[Config] = None

def load_config() -> Config:
    """تابع لود کردن تنظیمات برای رفع خطای main.py"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance

# متغیر پیش‌فرض آماده مصرف
config = load_config()
