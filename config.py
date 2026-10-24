# -*- coding: utf-8 -*-
"""config.py — خواندن و اعتبارسنجی تنظیمات (python-dotenv + pydantic)
OWNER_ID, BOT_TOKEN و شناسه‌ی ۹ موضوع (TOPIC_1 تا TOPIC_9) از متغیر محیطی خوانده می‌شوند؛ نام‌های معنایی قدیمی نیز پشتیبانی می‌شوند.
هیچ شناسه‌ی ساختگی‌ای تولید نمی‌شود؛ اگر متغیری نباشد، اعتبارسنجی خطا می‌دهد."""
from __future__ import annotations
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, Optional
from dotenv import load_dotenv

# کلیدهای داخلی پایدار؛ TOPIC_1..TOPIC_9 مطابق ترتیب موضوع‌های گروه‌اند.
TOPIC_KEYS = (
    "general", "podcast", "rules", "portfolio", "intro", "tariff",
    "projects", "reviews", "audio",
)

# Numbered environment variables are the public configuration API.
TOPIC_NUMBER_TO_KEY = {i: key for i, key in enumerate(TOPIC_KEYS, start=1)}
TOPIC_KEY_TO_NUMBER = {key: number for number, key in TOPIC_NUMBER_TO_KEY.items()}

TOPIC_ENV_KEYS = dict(zip(TOPIC_KEYS, (f"TOPIC_{i}" for i in range(1, 10))))
LEGACY_TOPIC_ENV_KEYS = {
    "general": "TOPIC_GENERAL", "podcast": "TOPIC_PODCAST",
    "rules": "TOPIC_RULES", "portfolio": "TOPIC_PORTFOLIO",
    "intro": "TOPIC_INTRO", "tariff": "TOPIC_TARIFF",
    "projects": "TOPIC_PROJECTS", "reviews": "TOPIC_REVIEWS",
    "audio": "TOPIC_AUDIO",
}

GENERAL_DAILY_LIMIT = 15  # سقف روزانه‌ی پیام هر کاربر در گفت‌وگوی عمومی (UTC تقویمی)

class ConfigError(Exception):
    """خطای اعتبارسنجی پیکربندی — مانع راه‌اندازی ربات می‌شود."""

@dataclass(frozen=True)
class Config:
    bot_token: str
    owner_id: int
    group_id: Optional[int]                      # شناسه عددی سوپرگروه (اختیاری؛ با /group_id قابل تنظیم)
    topics: Dict[str, int]                       # شناسه‌های واقعی Message Thread ID
    db_path: str
    banned_words_path: str
    timezone: str = "Asia/Tehran"                # منطقه‌ی زمانی مستندشده برای شمارش ماه/روز تقویمی
    general_rate_limit: int = 10                 # سقف پیام کاربران معمولی در ساعت در گفت‌وگوی عمومی (RATE_LIMIT_GENERAL_PER_HOUR)
    topic_names: Dict[str, str] = field(default_factory=lambda: dict(zip(TOPIC_KEYS, (
        "گفت‌وگوی عمومی گویندگان", "پادکست؛ تولید و تدوین", "قوانین و اطلاعیه‌ها",
        "نمونه‌کارهای گویندگی", "معرفی گویندگان حرفه‌ای", "تعرفه‌ها و قراردادهای گویندگی",
        "پروژه‌ها و درخواست‌های همکاری", "نقد و بررسی کارهای گویندگی", "ویرایش و بهینه‌سازی صدا",
    ))))
    # ثابت‌های قوانین (قابل تنظیم نیستند مگر با کد — مطابق متن قانون)
    general_hourly: int = 10
    general_daily: int = 15
    general_refresh_users: int = 5               # «پنج کاربر دیگر» = ۵ کاربرِ متمایزِ غیر از خودِ کاربر
    portfolio_weekly: int = 1
    portfolio_monthly: int = 3
    podcast_hourly: int = 3
    podcast_total: int = 12
    podcast_refresh_users: int = 5
    intro_monthly: int = 1
    tariff_edits_allowed: int = 1                # یک ویرایش مجاز در ماه
    penalty_mute1_hours: int = 24
    penalty_mute2_days: int = 7
    exempt_admins_from_penalties: bool = True    # پیش‌فرض امن: تنبیه خودکارِ مدیران/مالک خاموش

def _get_env(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        raise ConfigError(
            f"متغیر محیطی «{name}» تنظیم نشده است. آن را در .env یا Environment Variables در Render وارد کنید."
        )
    return val

def _get_topic_id(name: str) -> int:
    # شماره‌گذاری TOPIC_1..TOPIC_9 مرجع است؛ نام معنایی برای سازگاری عقب‌رو fallback است.
    env_name = TOPIC_ENV_KEYS[name]
    raw = os.environ.get(env_name, "").strip()
    if not raw:
        legacy_name = LEGACY_TOPIC_ENV_KEYS[name]
        raw = os.environ.get(legacy_name, "").strip()
        if raw:
            env_name = legacy_name
    if not raw:
        # موضوعات ناقص ربات را از کار نمی‌اندازند اما در گروه اعلام می‌شوند؛ مقدار 0 یعنی «تنظیم نشده»
        return 0
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"مقدار {env_name} باید عدد صحیح (شناسه پیام ریشه) باشد؛ مقدار فعلی: {raw!r}")

def load_config(env_file: Optional[str] = None) -> Config:
    """خواندن و اعتبارسنجی کامل پیکربندی. در صورت نقص اساسی، ConfigError پرتاب می‌شود."""
    if env_file and os.path.exists(env_file):
        load_dotenv(env_file)
    else:
        load_dotenv()  # پیش‌فرض .env کنار پروژه
    bot_token = _get_env("BOT_TOKEN")
    if ":" not in bot_token:
        raise ConfigError("BOT_TOKEN نامعتبر است؛ توکن را از BotFather دریافت کنید.")
    try:
        owner_id = int(_get_env("OWNER_ID"))
    except ValueError:
        raise ConfigError("OWNER_ID باید شناسه‌ی عددی تلگرامِ مالک باشد.")
    topics = {k: _get_topic_id(k) for k in TOPIC_KEYS}
    group_raw = os.environ.get("GROUP_ID", "").strip()
    group_id = int(group_raw) if group_raw.isdigit() else None
    try:
        general_rate_limit = int(os.environ.get("RATE_LIMIT_GENERAL_PER_HOUR", "10").strip() or "10")
    except ValueError:
        general_rate_limit = 10
    if general_rate_limit < 1:
        general_rate_limit = 10
    return Config(
        bot_token=bot_token,
        owner_id=owner_id,
        group_id=group_id,
        topics=topics,
        db_path=os.environ.get("DB_PATH", "bot_data.db"),
        banned_words_path=os.environ.get("BANNED_WORDS_PATH", "banned_words.txt"),
        general_rate_limit=general_rate_limit,
    )

def missing_topics(cfg: Config) -> list:
    """فهرست موضوعاتی که شناسه‌ی آن‌ها هنوز ثبت نشده است."""
    return [k for k, v in cfg.topics.items() if v == 0]

if __name__ == "__main__":
    # اجرای مستقل برای تست اعتبارسنجی: python config.py
    try:
        c = load_config()
        miss = missing_topics(c)
        print("پیکربندی معتبر است.", f"موضوعات تنظیم‌نشده: {miss}" if miss else "تمام موضوعات ثبت شده‌اند.")
    except ConfigError as e:
        print("خطای پیکربندی:", e, file=sys.stderr)
        sys.exit(1)
