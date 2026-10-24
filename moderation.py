import re
import os
import logging
from typing import Set, Tuple, Optional

logger = logging.getLogger(__name__)

class BannedWords:
    """کلاس بارگذاری و نرمال‌سازی کلمات ممنوعه"""
    def __init__(self, file_path: Optional[str] = None):
        if file_path is None:
            self.file_path = os.path.join(os.path.dirname(__file__), "banned_words.txt")
        else:
            self.file_path = file_path
        self.words: Set[str] = set()
        self.load()

    def load(self):
        self.words.clear()
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            norm = ModerationEngine.normalize_text(line)
                            if norm:
                                self.words.add(norm)
                logger.info(f"Loaded {len(self.words)} banned words successfully.")
            except Exception as e:
                logger.error(f"Error reading banned_words.txt: {e}")
        else:
            logger.warning(f"banned_words.txt not found at {self.file_path}")

class ModerationEngine:
    """موتور تحلیل محتوا، فیلتر کلمات و رفتارهای نامناسب"""
    def __init__(self, banned_words_path: Optional[str] = None):
        self.banned_words_loader = BannedWords(banned_words_path)

    @staticmethod
    def normalize_text(text: str) -> str:
        """نرمال‌سازی پیشرفته متن: حذف کشیدگی، اعراب، نیم‌فاصله‌ها و یکسان‌سازی حروف"""
        if not text:
            return ""
        # یکسان‌سازی ی و ک عربی
        text = text.replace("ي", "ی").replace("ك", "ک")
        # حذف اعراب و حرکات تنوین و تشدید
        text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
        # حذف کشیدگی حروف (تطویل)
        text = re.sub(r"ـ+", "", text)
        # حذف کاراکترهای نامرئی، نیم‌فاصله و فاصله‌های پنهان
        text = text.replace("\u200c", "").replace("\u200b", "").replace("\ufeff", "")
        return text.lower().strip()

    def check_banned_words(self, text: str) -> Tuple[bool, Optional[str]]:
        """تشخیص دقیق کلمات ممنوعه (ساده، فاصله‌دار، و شکسته مثل ک . س)"""
        if not text or not self.banned_words_loader.words:
            return False, None

        norm_text = self.normalize_text(text)
        words_in_text = norm_text.split()

        # ۱. بررسی تطابق کلمات مستقیم و عبارات ترکیبی
        for banned in self.banned_words_loader.words:
            pattern = r"(?:^|\s|[.,!؟_\-–/\\*+])" + re.escape(banned) + r"(?:$|\s|[.,!؟_\-–/\\*+])"
            if re.search(pattern, norm_text) or banned in words_in_text:
                return True, banned

        # ۲. بررسی کلمات شکسته و فاصله‌دار (Obfuscated)
        compressed_text = re.sub(r"[\s._\-–/\\*+]+", "", norm_text)
        for banned in self.banned_words_loader.words:
            clean_banned = re.sub(r"[\s._\-–/\\*+]+", "", banned)
            if len(clean_banned) >= 3 and clean_banned in compressed_text:
                return True, banned

        return False, None

# ایجاد نمونه یکتا (Singleton) برای استفاده توابع کمکی
_moderation_engine = ModerationEngine()

def check_banned_words(text: str) -> bool:
    is_banned, _ = _moderation_engine.check_banned_words(text)
    return is_banned

def normalize_text(text: str) -> str:
    return ModerationEngine.normalize_text(text)

async def check_duplicate_content(user_id: int, topic_id: int, text: str) -> bool:
    return False
