# -*- coding: utf-8 -*-
"""moderation.py — موتور بررسی قوانین و تنبیهات.
در تشخیص محتوای تخصصی/بازنویسی معنایی ادعای قطعی وجود ندارد؛ فقط سیگنال‌های قابل اتکا بررسی می‌شوند."""
from __future__ import annotations
import datetime as dt
import hashlib
import os
import html
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable
from database import Database, fingerprint

# نرمال‌سازی حروف رایج فارسی/عربی، نیم‌فاصله، علائم کشیده و فواصل غیرعادی.
CHAR_MAP = str.maketrans({
    "ي":"ی", "ى":"ی", "ك":"ک", "ة":"ه", "ۀ":"ه", "ؤ":"و", "إ":"ا", "أ":"ا", "ٱ":"ا",
    "ـ":"", "‌":" ", "‍":" ",
})

def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").translate(CHAR_MAP).lower()
    text = re.sub(r"[\u064b-\u065f\u0670]", "", text)
    text = re.sub(r"(.)\1{2,}", r"\1\1", text)  # محدودکردن کشیده‌ی نویسه (نه حذف کامل)
    text = re.sub(r"[^\w@:/-]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())

class BannedWords:
    def __init__(self, path: str, exceptions: Iterable[str] = ()):
        # مسیر پیش‌فرض نسبت به همین فایل (moderation.py) حل می‌شود، مستقل از cwd.
        if not os.path.isabs(path) and not os.path.exists(path):
            alt = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
            if os.path.exists(alt):
                path = alt
        self.path = path
        self.exceptions = {normalize_text(x) for x in exceptions}
        self.words: list[str] = []
        self.reload()

    def reload(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                raw_lines = f.readlines()
        except (FileNotFoundError, OSError):
            self.words = []
            return
        words: list[str] = []
        for line in raw_lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # سرصفحه‌های تزئینی فهرست (── ، 🔍 ، === ، تعداد کل: ...)
            if re.match(r"^(──|===|≡|\W*لیست|تعداد کل)", stripped):
                continue
            # حذف پیشوند عددی اختیاری مثل "12. " یا "3) "
            stripped = re.sub(r"^\s*\d+\s*[.)\-–:]\s*", "", stripped).strip()
            if not stripped or stripped.startswith("#"):
                continue
            w = normalize_text(stripped)
            if w:
                words.append(w)
        self.words = sorted(set(words), key=len, reverse=True)

    def find(self, text: str) -> str | None:
        norm = normalize_text(text or "")
        if not norm:
            return None
        # نسخه‌ی فشرده برای شکار حالت‌های حرف تکراری (کوون -> کون)
        compact = re.sub(r"(.)\1+", r"\1", norm)
        tokens = norm.split()
        padded = f" {norm} "
        padded_c = f" {compact} "
        for word in self.words:
            if not word or word in self.exceptions:
                continue
            if f" {word} " in padded or f" {word} " in padded_c:
                return word
            parts = word.split()
            if len(parts) == 1 and len(word) >= 5:
                # واژه‌های بلند: تطبیق درون‌واژه‌ای (پیوست‌شده/بدون فاصله)؛
                # قطعه‌های کوتاه برای جلوگیری از مثبت کاذب فقط با تطبیق کل توکن.
                if any(word in t or word in re.sub(r"(.)\1+", r"\1", t) for t in tokens):
                    return word
        return None

# لینک URL، دامنه، shorteners، لینک‌های t.me، username و متن دارای entity لینک
URL_RE = re.compile(r"(?i)(?:https?://|www\.|t\.me/|telegram\.me/|bit\.ly/|tinyurl\.com/|goo\.gl/|\b[a-z0-9-]+\.(?:com|net|org|ir|io|co|me|info|app|dev)\b)")
USERNAME_RE = re.compile(r"(?<!\w)@[A-Za-z][A-Za-z0-9_]{4,31}\b")

def has_link_or_ad(text: str, entities=(), forwarded: bool = False, forward_origin=None) -> bool:
    if forwarded or forward_origin is not None:
        return True
    if URL_RE.search(text or "") or USERNAME_RE.search(text or ""):
        return True
    # Telegram MessageEntity TEXT_LINK/URL/CUSTOM_EMOJI etc.; entity.type strings
    for entity in entities or ():
        if getattr(entity, "type", "") in ("text_link", "url"):
            return True
    return False

def text_fingerprint(text: str | None, file_ids: Iterable[str] = ()) -> str:
    # متمایزکردن متن-فقط، رسانه-فقط و ترکیبی؛ فایل تلگرام با file_unique_id در handler.
    parts = sorted(set(x for x in file_ids if x))
    return fingerprint(normalize_text(text or ""), "|".join(parts) if parts else None)

@dataclass
class Violation:
    rule: str
    details: str
    penalty_stage: int
    action: str
    # محدودیت‌هایی که باید به restrict_chat_member داده شوند.
    permissions: dict | None = None
    until: dt.datetime | None = None

class ModerationEngine:
    def __init__(self, db: Database, banned: BannedWords, owner_id: int | None = None):
        self.db, self.banned = db, banned
        self.owner_id = owner_id

    async def detect(self, text: str, entities=(), forwarded=False, forward_origin=None,
                     user_id: int | None = None):
        if self.owner_id is not None and user_id == self.owner_id:
            return None
        bad = self.banned.find(text)
        if bad:
            return "banned_word", "عبارت نامناسب (فقط دسته تخلف ثبت می‌شود)"
        if has_link_or_ad(text, entities, forwarded, forward_origin):
            return "link_ad", "لینک، نام کاربری یا پیام فورواردشده مجاز نیست"
        return None

    async def make_fingerprint(self, text: str, file_ids: Iterable[str], user_id: int,
                               chat_id: int, message_id: int, topic: str) -> bool:
        # Configured owner never participates in duplicate/fingerprint tracking.
        if self.owner_id is not None and user_id == self.owner_id:
            return True
        fp = text_fingerprint(text, file_ids)
        # متن خالی و بدون رسانه اثرانگشت معنادار ندارد
        if not (normalize_text(text or "") or list(file_ids)):
            return True
        return await self.db.check_and_store_hash(fp, user_id, chat_id, message_id, topic)

    async def record_violation(self, user_id: int, update_id: str, rule: str,
                               message_kind: str, chat_id: int, message_id: int,
                               details: str = "") -> Violation | None:
        """سطح تنبیه بر اساس سابقه پایدار؛ update_id یکتا جلوگیری از اجرای دوباره."""
        if self.owner_id is not None and user_id == self.owner_id:
            return None
        count_before = await self.db.count_violations(user_id)
        stage = min(count_before + 1, 4)
        actions = {1: "warning", 2: "mute24", 3: "mute7", 4: "ban"}
        saved = await self.db.add_violation(user_id, rule, update_id, message_kind,
                                            chat_id, message_id, "pending", details)
        if not saved:
            return None
        if stage == 1:
            action, until, perms = "warning", None, None
        elif stage == 2:
            action, until, perms = "mute24", dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=24), {
                "can_send_messages":False, "can_send_audios":False, "can_send_documents":False,
                "can_send_photos":False, "can_send_videos":False, "can_send_video_notes":False,
                "can_send_voice_notes":False, "can_send_polls":False, "can_send_other_messages":False,
                "can_add_web_page_previews":False, "can_invite_users":True, "can_pin_messages":True,
                "can_change_info":True, "can_manage_topics":True}
        elif stage == 3:
            action, until, perms = "mute7", dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=7), {
                "can_send_messages":False, "can_send_audios":False, "can_send_documents":False,
                "can_send_photos":False, "can_send_videos":False, "can_send_video_notes":False,
                "can_send_voice_notes":False, "can_send_polls":False, "can_send_other_messages":False,
                "can_add_web_page_previews":False, "can_invite_users":True, "can_pin_messages":True,
                "can_change_info":True, "can_manage_topics":True}
        else:
            action, until, perms = "ban", None, None
        # نتیجه اولیه pending است، handler پس از API موفقیت/شکست را ثبت می‌کند.
        return Violation(rule, details, stage, action, perms, until)

    async def set_action_result(self, violation_id: int, user_id: int, update_id: str,
                                action: str, success: bool):
        # شناسه‌ی تخلف: update_id یکتا؛ ثبت رخداد گزارش‌پذیر، داده‌ی اولیه دست‌نخورده
        await self.db.log_admin_event("action_result", f"user={user_id} update={update_id} action={action} success={success}")
