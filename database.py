import aiosqlite
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
from config import DATABASE_PATH, MAX_WARNINGS, WARNING_RESET_DAYS

logger = logging.getLogger(__name__)

async def init_db():
    """ایجاد جداول دیتابیس در صورت عدم وجود"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # جدول کاربران و اخطارها
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                warning_count INTEGER DEFAULT 0,
                last_warning_date TIMESTAMP,
                is_muted INTEGER DEFAULT 0,
                mute_until TIMESTAMP,
                is_banned INTEGER DEFAULT 0,
                ban_until TIMESTAMP
            )
        """)
        
        # جدول تاریخچه لاگ پیام‌ها و تخلفات
        await db.execute("""
            CREATE TABLE IF NOT EXISTS message_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                topic_id INTEGER,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # جدول شمارش محدودیت نرخ پیام‌ها
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                topic_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
    logger.info("Database initialized successfully.")

# ۱. ثبت پیام برای شمارش سقف ارسال (Rate Limiting)
async def record_user_message(user_id: int, topic_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO rate_limits (user_id, topic_id, timestamp) VALUES (?, ?, ?)",
            (user_id, topic_id, datetime.utcnow())
        )
        await db.commit()

# ۲. شمارش پیام‌های ۱ ساعت گذشته در تاپیک
async def get_user_message_count_hourly(user_id: int, topic_id: int) -> int:
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM rate_limits WHERE user_id = ? AND topic_id = ? AND timestamp >= ?",
            (user_id, topic_id, one_hour_ago)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

# ۳. شمارش پیام‌های ۲۴ ساعت گذشته در تاپیک
async def get_user_message_count_daily(user_id: int, topic_id: int) -> int:
    one_day_ago = datetime.utcnow() - timedelta(days=1)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM rate_limits WHERE user_id = ? AND topic_id = ? AND timestamp >= ?",
            (user_id, topic_id, one_day_ago)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

# ۴. لاگ کلی پیام (همان تابعی که رندر خطا گرفت)
async def log_message(user_id: int, topic_id: int, content: str = ""):
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                "INSERT INTO message_logs (user_id, topic_id, content, timestamp) VALUES (?, ?, ?, ?)",
                (user_id, topic_id, content[:500] if content else "", datetime.utcnow())
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Error logging message: {e}")

# ۵. سیستم اخطارها
async def add_warning(user_id: int, username: Optional[str] = None) -> int:
    now = datetime.utcnow()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT warning_count, last_warning_date FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()

        if row:
            count, last_date = row
            # ریست شدن خودکار اخطارها بعد از مدت زمان تعیین شده (مثلا ۳۰ روز)
            if last_date:
                try:
                    last_dt = datetime.fromisoformat(str(last_date))
                    if now - last_dt > timedelta(days=WARNING_RESET_DAYS):
                        count = 0
                except Exception:
                    pass
            new_count = count + 1
            await db.execute(
                "UPDATE users SET warning_count = ?, last_warning_date = ?, username = COALESCE(?, username) WHERE user_id = ?",
                (new_count, now, username, user_id)
            )
        else:
            new_count = 1
            await db.execute(
                "INSERT INTO users (user_id, username, warning_count, last_warning_date) VALUES (?, ?, ?, ?)",
                (user_id, username, new_count, now)
            )
        await db.commit()
        return new_count

async def get_warnings(user_id: int) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT warning_count FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def reset_warnings(user_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET warning_count = 0 WHERE user_id = ?", (user_id,))
        await db.commit()

# ۶. سیستم میوت و مسدودسازی (Mute & Ban)
async def is_user_muted(user_id: int) -> bool:
    now = datetime.utcnow()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT is_muted, mute_until FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False
            is_muted, mute_until = row
            if is_muted and mute_until:
                try:
                    until_dt = datetime.fromisoformat(str(mute_until))
                    if now < until_dt:
                        return True
                    else:
                        await db.execute("UPDATE users SET is_muted = 0, mute_until = NULL WHERE user_id = ?", (user_id,))
                        await db.commit()
                except Exception:
                    return bool(is_muted)
            return bool(is_muted)

async def is_user_banned(user_id: int) -> bool:
    now = datetime.utcnow()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT is_banned, ban_until FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False
            is_banned, ban_until = row
            if is_banned and ban_until:
                try:
                    until_dt = datetime.fromisoformat(str(ban_until))
                    if now < until_dt:
                        return True
                    else:
                        await db.execute("UPDATE users SET is_banned = 0, ban_until = NULL WHERE user_id = ?", (user_id,))
                        await db.commit()
                except Exception:
                    return bool(is_banned)
            return bool(is_banned)

async def mute_user(user_id: int, hours: int):
    mute_until = datetime.utcnow() + timedelta(hours=hours)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO users (user_id, is_muted, mute_until) VALUES (?, 1, ?) ON CONFLICT(user_id) DO UPDATE SET is_muted = 1, mute_until = ?",
            (user_id, mute_until, mute_until)
        )
        await db.commit()

async def unmute_user(user_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET is_muted = 0, mute_until = NULL WHERE user_id = ?", (user_id,))
        await db.commit()
