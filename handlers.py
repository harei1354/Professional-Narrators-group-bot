import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import Forbidden, BadRequest
from config import (
    GROUP_ID,
    TOPIC_GENERAL,
    TOPIC_PODCAST,
    TOPIC_RULES,
    TOPIC_PORTFOLIO,
    TOPIC_INTRO,
    TOPIC_TARIFF,
    TOPIC_PROJECTS,
    TOPIC_REVIEWS,
    TOPIC_AUDIO,
    GENERAL_HOURLY_LIMIT,
    GENERAL_DAILY_LIMIT,
    MAX_WARNINGS
)
from moderation import check_banned_words, check_duplicate_content, normalize_text
from database import (
    log_message,
    get_user_hourly_count,
    get_user_daily_count,
    add_warning,
    get_user_warnings,
    mute_user,
    is_user_muted
)

logger = logging.getLogger(__name__)

def get_actual_topic_id(update: Update) -> int:
    """تشخیص دقیق تاپیک شامل تاپیک عمومی"""
    thread_id = update.effective_message.message_thread_id
    if thread_id is None or thread_id == 0:
        return TOPIC_GENERAL
    return thread_id

async def send_private_warning(context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str) -> bool:
    """ارسال اخطار مستقیم در پی‌وی بدون افشا در گروه"""
    try:
        await context.bot.send_message(chat_id=user_id, text=text)
        return True
    except (Forbidden, BadRequest) as e:
        logger.warning(f"Could not send PV warning to {user_id}: {e}")
        return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user or user.is_bot:
        return

    # فقط در سوپرگروه هدف اجرا شود
    if chat.id != GROUP_ID:
        return

    user_id = user.id
    user_name = user.first_name or "کاربر"
    topic_id = get_actual_topic_id(update)
    text = message.text or message.caption or ""

    # ۱. بررسی میوت بودن کاربر
    if await is_user_muted(user_id):
        try:
            await message.delete()
        except Exception:
            pass
        return

    # ۲. فیلتر کلمات نامناسب و رکیک (اولین اولویت)
    if text and check_banned_words(text):
        try:
            await message.delete()
        except Exception as e:
            logger.error(f"Failed to delete banned word message: {e}")

        warn_count = await add_warning(user_id, "استفاده از الفاظ نامناسب")
        warn_msg = (
            f"سلام {user_name} عزیز،\n"
            f"پیام شما به دلیل استفاده از کلمات نامناسب در گروه حذف گردید.\n"
            f"اخطار دریافت شده: {warn_count} از {MAX_WARNINGS}."
        )
        if warn_count >= MAX_WARNINGS:
            await mute_user(chat.id, user_id, context.bot, duration_hours=24)
            warn_msg += "\nبه دلیل تکرار تخلف، دسترسی شما به مدت ۲۴ ساعت محدود شد."

        await send_private_warning(context, user_id, warn_msg)
        return

    # ۳. اعمال سقف و محدودیت در تاپیک گفتگوی عمومی
    if topic_id == TOPIC_GENERAL:
        hourly_count = await get_user_hourly_count(user_id, TOPIC_GENERAL)
        daily_count = await get_user_daily_count(user_id, TOPIC_GENERAL)

        if hourly_count >= GENERAL_HOURLY_LIMIT or daily_count >= GENERAL_DAILY_LIMIT:
            try:
                await message.delete()
            except Exception as e:
                logger.error(f"Failed to delete rate limited message: {e}")

            limit_msg = (
                f"سلام {user_name} عزیز،\n"
                f"سقف ارسال پیام شما در تاپیک «گفتگوی عمومی» تکمیل شده است.\n"
                f"محدودیت: حداکثر {GENERAL_HOURLY_LIMIT} پیام در ساعت و {GENERAL_DAILY_LIMIT} پیام در روز."
            )
            await send_private_warning(context, user_id, limit_msg)
            return

    # ۴. بررسی پیام‌های تکراری و اسپم
    if text and await check_duplicate_content(user_id, topic_id, text):
        try:
            await message.delete()
        except Exception:
            pass
        dup_msg = f"سلام {user_name}، لطفاً از ارسال پیام‌های تکراری و پشت سر هم خودداری کنید."
        await send_private_warning(context, user_id, dup_msg)
        return

    # ثبت پیام در دیتابیس برای شمارنده‌ها
    await log_message(user_id=user_id, topic_id=topic_id, text=text)
