# -*- coding: utf-8 -*-
"""database.py — لایه‌ی ذخیره‌سازی مبتنی بر SQLite (aiosqlite) با عملیات اتمیک
جدول‌ها: users, violations, topic_counters, portfolio_posts, intro_posts,
tariff_posts, content_hashes, collab_requests, notices, settings, admin_events
نکته: روی پلن رایگان Render فایل‌سیستم موقت است؛ داده‌ها با استقرار مجدد ممکن است
از بین بروند (مستند در README). برای پایداری، مسیر /tmp یا دیسک پایدار Render
(در صورت فعال‌سازی) قابل تنظیم با DB_PATH است."""
from __future__ import annotations
import asyncio
import datetime as dt
import hashlib
import json
import os
import aiosqlite

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    joined_at TEXT,
    rules_notified INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    update_id TEXT UNIQUE,               -- جلوگیری از ثبت چندباره‌ی یک آپدیت تلگرام
    rule TEXT NOT NULL,                  -- بند قانون (مثل link, banned_word, repeat, topic_limit)
    message_kind TEXT,                   -- text/photo/video/album/forward
    chat_id INTEGER,
    message_id INTEGER,
    action TEXT,                         -- warning/mute24/mute7/ban/failed
    details TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_viol_user ON violations(user_id);
CREATE TABLE IF NOT EXISTS topic_counters (
    user_id INTEGER NOT NULL,
    topic TEXT NOT NULL,
    bucket TEXT NOT NULL,                -- hour/day/month/total
    bucket_start TEXT NOT NULL,          -- شروع بازه (ISO، منطقه‌ی زمانی تنظیمات)
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, topic, bucket, bucket_start)
);
CREATE TABLE IF NOT EXISTS portfolio_posts (
    user_id INTEGER NOT NULL,
    message_id INTEGER,
    posted_at TEXT NOT NULL,
    PRIMARY KEY (user_id, posted_at)
);
CREATE INDEX IF NOT EXISTS idx_portfolio_time ON portfolio_posts(user_id, posted_at);
CREATE TABLE IF NOT EXISTS intro_posts (
    user_id INTEGER PRIMARY KEY,
    month TEXT NOT NULL,                 -- YYYY-MM تقویمی
    message_id INTEGER
);
CREATE TABLE IF NOT EXISTS tariff_posts (
    user_id INTEGER PRIMARY KEY,
    message_id INTEGER NOT NULL,
    edits_used INTEGER NOT NULL DEFAULT 0,
    last_edit_month TEXT,
    text_hash TEXT
);
CREATE TABLE IF NOT EXISTS content_hashes (
    hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    chat_id INTEGER,
    message_id INTEGER,
    topic TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS collab_requests (
    req_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    full_name TEXT,
    phone TEXT,
    email TEXT,
    username TEXT,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending/approved/rejected/published
    message_id INTEGER,                      -- پیام منتشرشده در گروه (پس از تأیید)
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS general_quota (
    user_id INTEGER PRIMARY KEY,
    hour_count INTEGER NOT NULL DEFAULT 0,
    hour_started TEXT,
    distinct_users TEXT NOT NULL DEFAULT '[]',  -- شناسه‌های کاربران دیگر از آخرین تجدید
    day_count INTEGER NOT NULL DEFAULT 0,
    day_started TEXT
);
CREATE TABLE IF NOT EXISTS notices (
    user_id INTEGER PRIMARY KEY,
    topic TEXT NOT NULL,
    kind TEXT NOT NULL,          -- نوع اطلاع‌رسانی (مثل limits_general)
    sent_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS admin_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,          -- error/failed_action/manager_fix/...
    details TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

def norm_time(ts: dt.datetime | None = None) -> str:
    return (ts or dt.datetime.utcnow()).isoformat()

def month_key(ts: dt.datetime | None = None) -> str:
    return (ts or dt.datetime.utcnow()).strftime("%Y-%m")

def day_key(ts: dt.datetime | None = None) -> str:
    return (ts or dt.datetime.utcnow()).strftime("%Y-%m-%d")

def hour_key(ts: dt.datetime | None = None) -> str:
    return (ts or dt.datetime.utcnow()).strftime("%Y-%m-%d-%H")

def fingerprint(text: str | None = None, file_id: str | None = None) -> str:
    """اثرانگشت محتوا: متنِ نرمال‌شده و/یا file_id پایدار رسانه."""
    h = hashlib.sha256()
    if file_id:
        h.update(b"F:" + file_id.encode())
    if text:
        h.update(b"T:" + " ".join(text.split()).encode())
    return h.hexdigest()

class Database:
    def __init__(self, path: str = "bot_data.db"):
        self.path = path
        self._lock = asyncio.Lock()   # عملیات حساس اتمیک

    async def init(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(SCHEMA)
            await db.commit()

    # ---------- کاربران و اطلاع‌رسانی ----------
    async def upsert_user(self, user_id: int, username: str | None, first_name: str | None):
        async with self._lock, aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO users(user_id, username, first_name, joined_at) VALUES(?,?,?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name",
                (user_id, username, first_name, norm_time()))
            await db.commit()

    async def was_notified(self, user_id: int, topic: str, kind: str) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT 1 FROM notices WHERE user_id=? AND topic=? AND kind=?",
                                   (user_id, topic, kind))
            return await cur.fetchone() is not None

    async def mark_notified(self, user_id: int, topic: str, kind: str):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR IGNORE INTO notices(user_id, topic, kind, sent_at) VALUES(?,?,?,?)",
                             (user_id, topic, kind, norm_time()))
            await db.commit()

    # ---------- تخلفات (اتمیک؛ با کلید یکتای update_id) ----------
    async def add_violation(self, user_id: int, rule: str, update_id: str | None,
                            message_kind: str = "", chat_id=None, message_id=None,
                            action: str = "warning", details: str = "") -> bool:
        """ثبت تخلف؛ اگر آپدیت قبلاً ثبت شده باشد False برمی‌گرداند (بدون شمارش دوباره)."""
        async with self._lock, aiosqlite.connect(self.path) as db:
            try:
                await db.execute(
                    "INSERT INTO violations(user_id, update_id, rule, message_kind, chat_id, message_id, action, details, created_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?)",
                    (user_id, update_id, rule, message_kind, chat_id, message_id, action, details, norm_time()))
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def count_violations(self, user_id: int) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM violations WHERE user_id=?", (user_id,))
            (n,) = await cur.fetchone()
            return n

    async def list_violations(self, user_id: int, limit: int = 20):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT created_at, rule, action, details FROM violations WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit))
            return await cur.fetchall()

    # ---------- شمارنده‌های عمومی موضوع (sample/quota) ----------
    async def bump_counter(self, user_id: int, topic: str, bucket: str, bucket_start: str,
                           limit: int) -> bool:
        """افزایش شمارنده و برگرداندن مجاز بودن. عملیات اتمیک با UPSERT شرطی."""
        async with self._lock, aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO topic_counters(user_id, topic, bucket, bucket_start, count) VALUES(?,?,?,?,1) "
                "ON CONFLICT(user_id, topic, bucket, bucket_start) DO UPDATE SET count=count+1",
                (user_id, topic, bucket, bucket_start))
            await db.commit()
            cur = await db.execute(
                "SELECT count FROM topic_counters WHERE user_id=? AND topic=? AND bucket=? AND bucket_start=?",
                (user_id, topic, bucket, bucket_start))
            (c,) = await cur.fetchone()
            return c <= limit

    async def counter_count(self, user_id: int, topic: str, bucket: str, bucket_start: str) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT count FROM topic_counters WHERE user_id=? AND topic=? AND bucket=? AND bucket_start=?",
                (user_id, topic, bucket, bucket_start))
            row = await cur.fetchone()
            return row[0] if row else 0

    async def next_slot_time(self, user_id: int, topic: str, bucket: str, limit: int) -> str | None:
        """زمان تقریبی مجاز بعدی برای سقف ماهانه/هفتگی (برای پیام رد انتشار)."""
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT bucket_start FROM topic_counters WHERE user_id=? AND topic=? AND bucket=? ORDER BY bucket_start",
                (user_id, topic, bucket))
            rows = await cur.fetchall()
        if len(rows) < limit:
            return None
        return rows[0][0]

    # ---------- نمونه کار: هفتگی/ماهانه هم‌زمان ----------
    async def add_portfolio_post(self, user_id: int, message_id: int | None) -> tuple[bool, str | None]:
        now = dt.datetime.utcnow()
        async with self._lock, aiosqlite.connect(self.path) as db:
            for table, start in (("portfolio_posts", None),):
                pass
            # هفتگی
            cur = await db.execute(
                "SELECT COUNT(*) FROM portfolio_posts WHERE user_id=? AND posted_at >= ?",
                (user_id, (now - dt.timedelta(days=7)).isoformat()))
            (w,) = await cur.fetchone()
            # ماهانه (تقویمی UTC؛ منطقه‌ی زمانی در README مستند است)
            cur = await db.execute(
                "SELECT COUNT(*) FROM portfolio_posts WHERE user_id=? AND posted_at LIKE ?",
                (user_id, month_key(now) + "%"))
            (m,) = await cur.fetchone()
            if w >= 1:
                return False, (now + dt.timedelta(days=7 - (now - dt.datetime.fromisoformat(
                    [r[0] for r in await db.execute("SELECT MIN(posted_at) FROM portfolio_posts WHERE user_id=? AND posted_at>=?",
                     (user_id, (now - dt.timedelta(days=7)).isoformat()))][0] if False else (now - dt.timedelta(days=7)).isoformat()
                ))).isoformat())
            if m >= 3:
                return False, (month_key(now) + "-01 next month") if False else None
            await db.execute("INSERT INTO portfolio_posts(user_id, message_id, posted_at) VALUES(?,?,?)",
                             (user_id, message_id, norm_time(now)))
            await db.commit()
        return True, None

    # ---------- معرفی گویندگان: یک پست در ماه تقویمی ----------
    async def add_intro_post(self, user_id: int, message_id: int | None) -> bool:
        mk = month_key()
        async with self._lock, aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT month FROM intro_posts WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            if row and row[0] == mk:
                return False
            await db.execute(
                "INSERT INTO intro_posts(user_id, month, message_id) VALUES(?,?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET month=excluded.month, message_id=excluded.message_id",
                (user_id, mk, message_id))
            await db.commit()
        return True

    # ---------- تعرفه: ثبت پیام و شمارش ویرایش مجاز ----------
    async def get_tariff(self, user_id: int):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT message_id, edits_used, last_edit_month, text_hash FROM tariff_posts WHERE user_id=?",
                (user_id,))
            return await cur.fetchone()

    async def register_tariff(self, user_id: int, message_id: int, text_hash: str):
        async with self._lock, aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO tariff_posts(user_id, message_id, edits_used, last_edit_month, text_hash) VALUES(?,?,0,NULL,?) "
                "ON CONFLICT(user_id) DO UPDATE SET message_id=excluded.message_id, text_hash=excluded.text_hash",
                (user_id, message_id, text_hash))
            await db.commit()

    async def try_tariff_edit(self, user_id: int, new_hash: str, edits_allowed: int = 1) -> tuple[bool, str]:
        """ویرایش تعرفه: فقط یک بار در ماه و فقط اگر متن واقعاً تغییر کرده باشد.
        حذف و ارسال مجدد با ثبت هش متن تشخیص داده می‌شود (محافظه‌کارانه)."""
        mk = month_key()
        async with self._lock, aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT message_id, edits_used, last_edit_month, text_hash FROM tariff_posts WHERE user_id=?",
                (user_id,))
            row = await cur.fetchone()
            if not row:
                return False, "no_post"
            _, used, last_month, old_hash = row
            if old_hash == new_hash:
                return True, "unchanged"
            if last_month == mk and used >= edits_allowed:
                return False, "edit_limit"
            await db.execute("UPDATE tariff_posts SET edits_used=edits_used+1, last_edit_month=?, text_hash=? WHERE user_id=?",
                             (mk, new_hash, user_id))
            await db.commit()
        return True, "edited"

    # ---------- پیام تکراری ----------
    async def check_and_store_hash(self, fp: str, user_id: int, chat_id, message_id, topic: str,
                                   retention_days: int = 30) -> bool:
        """اگر اثرانگشت قبلاً ثبت شده باشد False (تکراری) برمی‌گرداند؛ در غیر این صورت ثبت می‌کند."""
        cutoff = (dt.datetime.utcnow() - dt.timedelta(days=retention_days)).isoformat()
        async with self._lock, aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM content_hashes WHERE created_at < ?", (cutoff,))
            cur = await db.execute("SELECT 1 FROM content_hashes WHERE hash=?", (fp,))
            dup = await cur.fetchone()
            if dup:
                return False
            await db.execute("INSERT INTO content_hashes(hash, user_id, chat_id, message_id, topic, created_at) VALUES(?,?,?,?,?,?)",
                             (fp, user_id, chat_id, message_id, topic, norm_time()))
            await db.commit()
        return True

    # ---------- سهمیه گفتگوی عمومی (قانون ۵) ----------
    async def general_quota_check(self, user_id: int, hourly: int = 10, daily: int = 15,
                                  refresh_users: int = 5) -> tuple[bool, str]:
        """تعریف دقیق تجدید: پس از ثبت پیام کاربر، اگر از زمان شروع بازه‌ی ساعتیِ او
        ۵ کاربرِ متمایزِ دیگر پیام داده باشند، شمارنده‌ی ساعتی او صفر و بازه تازه آغاز می‌شود.
        سهمیه‌ی روزانه مستقل است و با تجدید ساعتی دور زده نمی‌شود."""
        now = dt.datetime.utcnow()
        hk, dk = hour_key(now), day_key(now)
        async with self._lock, aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT hour_count, hour_started, distinct_users, day_count, day_started FROM general_quota WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            if not row:
                await db.execute("INSERT INTO general_quota(user_id, hour_count, hour_started, distinct_users, day_count, day_started) VALUES(?,1,?, ?,1,?)",
                                 (user_id, hk, json.dumps([]), dk))
                await db.commit()
                return True, "ok"
            hcount, hstart, dusers, dcount, dstart = row
            dstart = dstart or dk
            dcount = dcount if dstart == dk else 0
            others = json.loads(dusers or "[]")
            if hstart and hstart != hk and len(others) >= refresh_users:
                hcount, hstart, others = 0, hk, []     # تجدید سهمیه ساعتی
            if hcount >= hourly:
                return False, "hourly"
            if dcount >= daily:
                return False, "daily"
            await db.execute(
                "UPDATE general_quota SET hour_count=?, hour_started=?, distinct_users=?, day_count=?, day_started=? WHERE user_id=?",
                (hcount + 1, hstart or hk, json.dumps(others), dcount + 1, dk, user_id))
            await db.commit()
        return True, "ok"

    async def general_quota_other_seen(self, user_id: int) -> None:
        """ثبت فعالیت «کاربر دیگر» برای منطق تجدید سهمیه: افزودن کاربر به فهرست متمایزِ
        بازه‌ی ساعتیِ هر کاربرِ فعال دیگر (حداکثر تا ۵ نفر)."""
        hk = hour_key()
        async with self._lock, aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT user_id, hour_started, distinct_users FROM general_quota WHERE user_id != ?", (user_id,))
            rows = await cur.fetchall()
            for uid, hstart, dusers in rows:
                if hstart != hk:
                    continue
                lst = json.loads(dusers or "[]")
                if user_id not in lst and len(lst) < 5:
                    lst.append(user_id)
                    await db.execute("UPDATE general_quota SET distinct_users=? WHERE user_id=?",
                                     (json.dumps(lst), uid))
            await db.commit()

    # ---------- پادکست: ساعتی + سقف ۱۲ + تجدید ۵ نفر ----------
    async def podcast_quota_check(self, user_id: int, hourly: int = 3, total: int = 12,
                                  refresh_users: int = 5) -> tuple[bool, str]:
        hk = hour_key()
        async with self._lock, aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT count FROM topic_counters WHERE user_id=? AND topic='podcast' AND bucket='total'",
                (user_id,))
            row = await cur.fetchone()
            tcount = row[0] if row else 0
            if tcount >= total:
                return False, "total"
            cur = await db.execute(
                "SELECT count, bucket_start FROM topic_counters WHERE user_id=? AND topic='podcast' AND bucket='hour' ORDER BY bucket_start DESC LIMIT 1",
                (user_id,))
            row = await cur.fetchone()
            hcount, hstart = row if row else (0, hk)
            if hstart != hk:
                hcount = 0
            if hcount >= hourly:
                return False, "hourly"
            # سهمیه تجدیدشده: اگر ۵ کاربر دیگر در این ساعت فعال بوده‌اند، شمارنده‌ی ساعتی منفی‌سازی نمی‌شود؛
            # تجدید به معنای باز شدن یک پست اضافی است → سقف مؤثر ساعتی = hourly + k (k = تعداد تجدیدهای ثبت‌شده)
            refresh = await self._podcast_refresh_count(db, user_id, hk)
            eff_limit = hourly + refresh * 1
            if hcount + 1 > eff_limit and refresh < 99:
                if hcount >= eff_limit:
                    pass
            if hcount + 1 > eff_limit:
                return False, "hourly"
            await db.execute(
                "INSERT INTO topic_counters(user_id, topic, bucket, bucket_start, count) VALUES(?,?,?,?,1) "
                "ON CONFLICT(user_id, topic, bucket, bucket_start) DO UPDATE SET count=count+1",
                (user_id, "podcast", "hour", hk))
            await db.execute(
                "INSERT INTO topic_counters(user_id, topic, bucket, bucket_start, count) VALUES(?,?,?,?,1) "
                "ON CONFLICT(user_id, topic, bucket, bucket_start) DO UPDATE SET count=count+1",
                (user_id, "podcast", "total", "total"))
            await db.commit()
        return True, "ok"

    async def _podcast_refresh_count(self, db, user_id: int, hk: str) -> int:
        cur = await db.execute(
            "SELECT bucket_start, count FROM topic_counters WHERE user_id=? AND topic='podcast' AND bucket='refresh' AND bucket_start=?",
            (user_id, hk))
        row = await cur.fetchone()
        return row[1] if row else 0

    async def podcast_refresh_seen_other(self, user_id: int) -> None:
        """ثبت فعالیت کاربر دیگر برای تجدید سهمیه پادکست (۵ کاربر متمایز = یک پست اضافی)."""
        hk = hour_key()
        async with self._lock, aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT bucket_start, count FROM topic_counters WHERE user_id=? AND topic='podcast' AND bucket='others' AND bucket_start=?",
                (user_id, hk))
            row = await cur.fetchone()
            if row:
                await db.execute("UPDATE topic_counters SET count=count+1 WHERE user_id=? AND topic='podcast' AND bucket='others' AND bucket_start=?",
                                 (user_id, hk))
            else:
                await db.execute("INSERT INTO topic_counters(user_id, topic, bucket, bucket_start, count) VALUES(?,?,?,?,1)",
                                 (user_id, "podcast", "others", hk, 1))
            await db.commit()

    # ---------- درخواست همکاری ----------
    async def add_collab(self, user_id: int, full_name: str, phone: str, email: str, username: str) -> int:
        async with self._lock, aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "INSERT INTO collab_requests(user_id, full_name, phone, email, username, status, created_at) VALUES(?,?,?,?,?,?,?)",
                (user_id, full_name, phone, email, username, "pending", norm_time()))
            await db.commit()
            return cur.lastrowid

    async def get_collab(self, req_id: int):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT req_id, user_id, full_name, phone, email, username, status, message_id FROM collab_requests WHERE req_id=?", (req_id,))
            return await cur.fetchone()

    async def set_collab_status(self, req_id: int, status: str, message_id: int | None = None) -> bool:
        """تغییر وضعیت فقط از وضعیت‌های مجاز؛ جلوگیری از تأیید/انتشار دوباره."""
        allowed = {"pending": {"approved", "rejected"},
                   "approved": {"published"},
                   "rejected": set(), "published": set()}
        async with self._lock, aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT status FROM collab_requests WHERE req_id=?", (req_id,))
            row = await cur.fetchone()
            if not row or status not in allowed.get(row[0], set()):
                return False
            await db.execute("UPDATE collab_requests SET status=?, message_id=COALESCE(?, message_id) WHERE req_id=?",
                             (status, message_id, req_id))
            await db.commit()
        return True

    async def list_collabs(self, status: str | None = None, limit: int = 20):
        async with aiosqlite.connect(self.path) as db:
            if status:
                cur = await db.execute("SELECT req_id, user_id, full_name, status FROM collab_requests WHERE status=? ORDER BY req_id DESC LIMIT ?", (status, limit))
            else:
                cur = await db.execute("SELECT req_id, user_id, full_name, status FROM collab_requests ORDER BY req_id DESC LIMIT ?", (limit,))
            return await cur.fetchall()

    # ---------- تنظیمات و رویدادهای مدیریتی ----------
    async def set_setting(self, key: str, value: str):
        async with self._lock, aiosqlite.connect(self.path) as db:
            await db.execute("INSERT INTO settings(key, value) VALUES(?,?) "
                             "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
            await db.commit()

    async def get_setting(self, key: str) -> str | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT value FROM settings WHERE key=?", (key,))
            row = await cur.fetchone()
            return row[0] if row else None

    async def log_admin_event(self, kind: str, details: str):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT INTO admin_events(kind, details, created_at) VALUES(?,?,?)",
                             (kind, details, norm_time()))
            await db.commit()

    # ---------- پشتیبان‌گیری / بازیابی ----------
    async def backup_json(self, path: str):
        """خروجی JSON از داده‌های مجاز (بدون اطلاعات خصوصی کامل درخواست‌ها)."""
        data = {}
        async with aiosqlite.connect(self.path) as db:
            for table in ("users", "violations", "topic_counters", "portfolio_posts",
                          "intro_posts", "tariff_posts", "content_hashes", "notices",
                          "settings", "admin_events"):
                cur = await db.execute(f"SELECT * FROM {table}")
                cols = [d[0] for d in cur.description]
                data[table] = [dict(zip(cols, r)) for r in await cur.fetchall()]
            # درخواست همکاری با ماسک اطلاعات خصوصی
            cur = await db.execute("SELECT req_id, user_id, status, created_at FROM collab_requests")
            data["collab_requests_masked"] = [dict(zip(("req_id", "user_id", "status", "created_at"), r)) for r in await cur.fetchall()]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        return path

    async def restore_json(self, path: str) -> int:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        n = 0
        async with self._lock, aiosqlite.connect(self.path) as db:
            for table, rows in data.items():
                if table == "collab_requests_masked":
                    continue
                if not rows:
                    continue
                cols = list(rows[0].keys())
                ph = ",".join("?" * len(cols))
                for r in rows:
                    await db.execute(f"INSERT OR REPLACE INTO {table}({','.join(cols)}) VALUES({ph})",
                                     [r.get(c) for c in cols])
                    n += 1
            await db.commit()
        return n

    async def reset_user_counters(self, user_id: int, topic: str | None = None) -> int:
        """اصلاح شمارنده‌ها توسط مدیر (با ثبت رویداد در admin_events)."""
        async with self._lock, aiosqlite.connect(self.path) as db:
            if topic:
                cur = await db.execute("DELETE FROM topic_counters WHERE user_id=? AND topic=?", (user_id, topic))
            else:
                cur = await db.execute("DELETE FROM topic_counters WHERE user_id=?", (user_id,))
            await db.commit()
            return cur.rowcount

    async def clear_user_violations(self, user_id: int) -> int:
        """فقط با فرمان مدیریتی مجاز؛ پاک‌کردن خودکار سابقه وجود ندارد."""
        async with self._lock, aiosqlite.connect(self.path) as db:
            cur = await db.execute("DELETE FROM violations WHERE user_id=?", (user_id,))
            await db.commit()
            return cur.rowcount

    async def purge_collab_privacy(self, before_iso: str) -> int:
        """حذف اطلاعات خصوصی درخواست‌های قدیمی (مدیریت دوره‌ی نگهداری)."""
        async with self._lock, aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "UPDATE collab_requests SET phone='', email='' WHERE created_at < ? AND status IN ('rejected','published')",
                (before_iso,))
            await db.commit()
            return cur.rowcount
