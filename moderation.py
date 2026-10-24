import re
import os
import logging

logger = logging.getLogger(__name__)

BANNED_WORDS = set()

def load_banned_words():
    global BANNED_WORDS
    BANNED_WORDS.clear()
    file_path = os.path.join(os.path.dirname(__file__), "banned_words.txt")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                word = line.strip().lower()
                if word and not word.startswith("#"):
                    BANNED_WORDS.add(word)
        logger.info(f"Loaded {len(BANNED_WORDS)} banned words.")
    else:
        logger.warning("banned_words.txt not found!")

def normalize_text(text: str) -> str:
    """نرمال‌سازی پیشرفته برای کشف کلمات چسبیده، فاصله‌دار و کشیده"""
    if not text:
        return ""
    # تبدیل ی و ک عربی به فارسی
    text = text.replace("ي", "ی").replace("ك", "ک")
    # حذف اعراب و حرکات
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
    # حذف کشیدگی حروف (تطویل مثل کــــس)
    text = re.sub(r"ـ+", "", text)
    # حذف نیم‌فاصله و کاراکترهای مخفی
    text = text.replace("\u200c", "").replace("\u200b", "").replace("\ufeff", "")
    return text.lower()

def check_banned_words(text: str) -> bool:
    if not BANNED_WORDS:
        load_banned_words()

    norm_text = normalize_text(text)
    
    # ۱. بررسی ساده کلمات و ترکیبات
    for word in BANNED_WORDS:
        # جستجو در متن نرمال
        pattern = r"(?:^|\s|[.,!؟_-])" + re.escape(word) + r"(?:$|\s|[.,!؟_-])"
        if re.search(pattern, norm_text):
            return True
        if word in norm_text.split():
            return True

    # ۲. بررسی کلمات شکسته (مثل: ک . س یا ک - ی - ر)
    compressed_text = re.sub(r"[\s._\-–/\\*+]+", "", norm_text)
    for word in BANNED_WORDS:
        clean_word = re.sub(r"[\s._\-–/\\*+]+", "", word)
        if len(clean_word) >= 3 and clean_word in compressed_text:
            return True

    return False

async def check_duplicate_content(user_id: int, topic_id: int, text: str) -> bool:
    # متصل به بررسی دیتابیس برای جلوگیری از ارسال پیام یکسان پشت سر هم
    return False
