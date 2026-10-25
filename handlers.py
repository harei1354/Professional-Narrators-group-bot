# -*- coding: utf-8 -*-
"""handlers.py — فرمان‌ها، درخواست همکاری خصوصی و رسیدگی به پیام‌های گروه."""
from __future__ import annotations
import datetime as dt, html, os, re
from telegram import Update, ChatPermissions, InputFile
from telegram.constants import ChatType
from telegram.ext import (Application, CommandHandler, MessageHandler, ConversationHandler,
                          ContextTypes, filters)
from telegram.error import TelegramError, BadRequest, Forbidden
from config import Config, TOPIC_KEYS
from database import Database, fingerprint
from moderation import ModerationEngine, BannedWords, normalize_text

FULL, PHONE, EMAIL = range(3)
TOPIC_NAMES = {
    "general": "گفت‌وگوی عمومی گویندگان",
    "podcast": "پادکست؛ تولید و تدوین",
    "rules": "قوانین و اطلاعیه‌ها",
    "portfolio": "نمونه‌کارهای گویندگی",
    "intro": "معرفی گویندگان حرفه‌ای",
    "tariff": "تعرفه‌ها و قراردادهای گویندگی",
    "projects": "پروژه‌ها و درخواست‌های همکاری",
    "reviews": "نقد و بررسی کارهای گویندگی",
    "audio": "ویرایش و بهینه‌سازی صدا",
}

def ctx_objects(context): return context.application.bot_data["cfg"], context.application.bot_data["db"]
def is_owner(update, cfg): return bool(update.effective_user and update.effective_user.id == cfg.owner_id)
async def is_admin(update, context, cfg):
    if is_owner(update,cfg): return True
    if not update.effective_chat or not update.effective_user: return False
    try:
        m=await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        return m.status in ("administrator","creator")
    except TelegramError: return False

def topic_key(message, cfg):
    """Resolve a Telegram thread id to exactly one of the nine configured topics.

    None (General topic) maps to "general" whenever the general topic is
    configured with id None, 0 or 1 — Telegram sends message_thread_id=None
    for messages in the General topic.
    """
    tid = getattr(message, "message_thread_id", None)
    for key in TOPIC_KEYS:
        if cfg.topics.get(key) and cfg.topics[key] == tid:
            return key
    if tid is None or tid in (0, 1):
        cfg_general = cfg.topics.get("general")
        if cfg_general in (None, 0, 1) or "general" in TOPIC_KEYS and cfg_general == tid:
            return "general"
    return None

def message_kind(m):
    if m.photo:return "photo"
    if m.video:return "video"
    if m.document:return "document"
    if m.voice or m.audio:return "audio"
    if m.animation:return "animation"
    return "text"

def file_ids(m):
    out=[]
    for attr in ("photo","video","document","audio","voice","animation","video_note"):
        obj=getattr(m,attr,None)
        if obj:
            if isinstance(obj,list): out.extend(x.file_unique_id for x in obj)
            else: out.append(obj.file_unique_id)
    return out

async def help_cmd(u,c):
    await u.effective_message.reply_text("راهنمای ربات گویندگان حرفه‌ای\nدستورات اعضا: /help، /collab\nمدیر: /status، /topic_id، /group_id، /warnings ID، /history ID، /unmute ID، /set_topic KEY ID، /collabs، /approve ID، /reject ID، /backup، /restore (پیوست فایل JSON)، /reset_counter ID [topic]\nبرای ثبت درخواست همکاری، ابتدا در گفت‌وگوی خصوصی ربات /collab را بزنید.")
async def status_cmd(u,c):
    cfg,db=ctx_objects(c)
    if not await is_admin(u,c,cfg): return await u.effective_message.reply_text("این فرمان فقط برای مدیران گروه است.")
    missing=[k for k,v in cfg.topics.items() if not v]
    await u.effective_message.reply_text(f"ربات فعال است. گروه={cfg.group_id or 'ثبت‌نشده'}؛ پایگاه داده={cfg.db_path}\nموضوعات ناقص: {', '.join(missing) or 'هیچ‌کدام'}\nمدیران از تنبیه خودکار معاف‌اند.")
async def topic_id(u,c):
    m=u.effective_message
    await m.reply_text(f"chat_id={m.chat_id}\nmessage_thread_id={getattr(m,'message_thread_id',None)}\nmessage_id={m.message_id}\nبرای شناسایی تاپیک، از message_thread_id استفاده کنید؛ شناسهٔ موضوع را در TOPIC_1..TOPIC_9 ثبت کنید (ترتیب در README_FA.md).")
async def group_id(u,c): await u.effective_message.reply_text(f"شناسه گروه: {u.effective_chat.id}")
async def warnings(u,c):
    cfg,db=ctx_objects(c)
    if not await is_admin(u,c,cfg): return await u.effective_message.reply_text("دسترسی ندارید.")
    if not c.args or not c.args[0].lstrip('-').isdigit(): return await u.effective_message.reply_text("کاربرد: /warnings شناسه_کاربر")
    uid=int(c.args[0]); await u.effective_message.reply_text(f"کاربر {uid}: {await db.count_violations(uid)} تخلف ثبت‌شده.")
async def history(u,c):
    cfg,db=ctx_objects(c)
    if not await is_admin(u,c,cfg): return await u.effective_message.reply_text("دسترسی ندارید.")
    if not c.args or not c.args[0].lstrip('-').isdigit(): return await u.effective_message.reply_text("کاربرد: /history شناسه_کاربر")
    rows=await db.list_violations(int(c.args[0])); text="\n".join(f"{a} | {b} | {d}" for a,b,_,d in rows) or "سابقه‌ای نیست."
    await u.effective_message.reply_text(text[:4000])
async def set_topic(u,c):
    cfg,db=ctx_objects(c)
    if not is_owner(u,cfg): return await u.effective_message.reply_text("فقط مالک ربات مجاز است.")
    if len(c.args)!=2 or c.args[0] not in TOPIC_KEYS or not c.args[1].isdigit(): return await u.effective_message.reply_text("کاربرد: /set_topic general 123 یا /set_topic reviews 473 (فقط OWNER_ID)")
    await db.set_setting("topic_"+c.args[0],c.args[1]); await u.effective_message.reply_text("ثبت شد؛ برای فعال‌سازی فوری، مقدار TOPIC_* را در تنظیمات Render نیز به‌روز و سرویس را راه‌اندازی مجدد کنید.")
async def unmute(u,c):
    cfg,db=ctx_objects(c)
    if not await is_admin(u,c,cfg): return await u.effective_message.reply_text("دسترسی ندارید.")
    if not c.args or not c.args[0].lstrip('-').isdigit(): return await u.effective_message.reply_text("کاربرد: /unmute شناسه_کاربر")
    perms=ChatPermissions(can_send_messages=True,can_send_audios=True,can_send_documents=True,can_send_photos=True,can_send_videos=True,can_send_video_notes=True,can_send_voice_notes=True,can_send_polls=True,can_send_other_messages=True,can_add_web_page_previews=True)
    try: await c.bot.restrict_chat_member(u.effective_chat.id,int(c.args[0]),permissions=perms); await db.log_admin_event("unmute",f"by={u.effective_user.id} user={c.args[0]}"); await u.effective_message.reply_text("رفع محدودیت انجام شد.")
    except TelegramError: await u.effective_message.reply_text("عملیات ناموفق بود؛ مجوز Restrict members و شناسه را بررسی کنید.")
async def collabs(u,c):
    cfg,db=ctx_objects(c)
    if not await is_admin(u,c,cfg): return await u.effective_message.reply_text("دسترسی ندارید.")
    rows=await db.list_collabs("pending")
    await u.effective_message.reply_text("درخواست‌های در انتظار:\n"+("\n".join(f"#{r[0]} کاربر {r[1]} — {r[2]}" for r in rows) or "موردی نیست."))
async def decide_collab(u,c,approved):
    cfg,db=ctx_objects(c)
    if not await is_admin(u,c,cfg): return await u.effective_message.reply_text("دسترسی ندارید.")
    if not c.args or not c.args[0].isdigit(): return await u.effective_message.reply_text("شناسه درخواست لازم است.")
    rid=int(c.args[0]); row=await db.get_collab(rid)
    if not row or row[6]!="pending": return await u.effective_message.reply_text("درخواست پیدا نشد یا قبلاً بررسی شده است.")
    if not approved:
        ok=await db.set_collab_status(rid,"rejected"); return await u.effective_message.reply_text("رد شد." if ok else "تغییر وضعیت ناموفق.")
    if not cfg.group_id: return await u.effective_message.reply_text("GROUP_ID تنظیم نشده؛ درخواست حفظ شد.")
    topic=cfg.topics.get("projects")
    if not topic: return await u.effective_message.reply_text("شناسهٔ موضوع پروژه‌ها تنظیم نشده است (TOPIC_7 / TOPIC_PROJECTS).")
    # فقط پس از تأیید مدیر اطلاعات تماس در تاپیک مجاز منتشر می‌شود؛ کاربر قبلاً از انتشار عمومی آگاه می‌شود.
    text=f"درخواست همکاری #{rid}\nنام: {html.escape(row[2] or '')}\nتلفن: {html.escape(row[3] or '')}\nایمیل: {html.escape(row[4] or '')}\nنام کاربری: {html.escape(row[5] or '')}"
    try:
        msg=await c.bot.send_message(cfg.group_id,text,message_thread_id=topic,parse_mode="HTML")
        ok=await db.set_collab_status(rid,"approved")
        if ok: await db.set_collab_status(rid,"published",msg.message_id)
        await u.effective_message.reply_text("تأیید و انتشار انجام شد." if ok else "انتشار شد اما تغییر وضعیت شکست خورد؛ بررسی دستی لازم است.")
    except TelegramError: await u.effective_message.reply_text("انتشار ناموفق بود؛ درخواست همچنان در انتظار بررسی است.")
async def approve(u,c): return await decide_collab(u,c,True)
async def reject(u,c): return await decide_collab(u,c,False)
async def backup(u,c):
    cfg,db=ctx_objects(c)
    if not is_owner(u,cfg): return await u.effective_message.reply_text("فقط مالک مجاز است.")
    path="/tmp/bot_backup.json"; await db.backup_json(path)
    with open(path,"rb") as f: await u.effective_message.reply_document(f,filename="bot_backup.json",caption="پشتیبان؛ درخواست‌ها فقط با اطلاعات ماسک‌شده.")
async def restore(u,c):
    cfg,db=ctx_objects(c)
    if not is_owner(u,cfg): return await u.effective_message.reply_text("فقط مالک مجاز است.")
    doc=u.effective_message.document
    if not doc or not doc.file_name.endswith(".json"): return await u.effective_message.reply_text("فایل JSON پشتیبان را به دستور /restore پیوست کنید.")
    f=await doc.get_file(); await f.download_to_drive("/tmp/restore.json")
    try: n=await db.restore_json("/tmp/restore.json"); await u.effective_message.reply_text(f"بازیابی شد؛ {n} ردیف.")
    except Exception: await u.effective_message.reply_text("فایل پشتیبان نامعتبر است؛ داده تغییر نکرده یا بازیابی ناقص است.")
async def reset_counter(u,c):
    cfg,db=ctx_objects(c)
    if not is_owner(u,cfg): return await u.effective_message.reply_text("فقط مالک مجاز است.")
    if not c.args or not c.args[0].isdigit(): return await u.effective_message.reply_text("کاربرد: /reset_counter ID [topic]")
    n=await db.reset_user_counters(int(c.args[0]),c.args[1] if len(c.args)>1 else None)
    await db.log_admin_event("manager_fix",f"by={u.effective_user.id} user={c.args[0]} topic={c.args[1:]}")
    await u.effective_message.reply_text(f"{n} شمارنده حذف شد (سوابق تخلف تغییر نکرد).")

# مکالمه خصوصی مرحله‌ای
async def collab_start(u,c):
    if u.effective_chat.type!=ChatType.PRIVATE: return await u.effective_message.reply_text("برای محرمانگی، ربات را در خصوصی باز و /start سپس /collab را ارسال کنید.")
    await u.effective_message.reply_text("درخواست همکاری — نام و نام خانوادگی کامل را بفرستید:"); return FULL
async def full_name(u,c):
    value=(u.effective_message.text or "").strip()
    if len(value)<3 or len(value)>150: await u.effective_message.reply_text("نام کامل معتبر نیست؛ دوباره وارد کنید."); return FULL
    c.user_data["full_name"]=value; await u.effective_message.reply_text("شماره تلفن را با کد کشور وارد کنید:"); return PHONE
async def phone(u,c):
    value=(u.effective_message.text or "").strip()
    if len(re.sub(r"\D","",value))<7: await u.effective_message.reply_text("شماره معتبر نیست؛ دوباره وارد کنید."); return PHONE
    c.user_data["phone"]=value; await u.effective_message.reply_text("ایمیل را وارد کنید:"); return EMAIL
async def email(u,c):
    value=(u.effective_message.text or "").strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",value): await u.effective_message.reply_text("ایمیل معتبر نیست؛ دوباره وارد کنید."); return EMAIL
    cfg,db=ctx_objects(c); user=u.effective_user
    rid=await db.add_collab(user.id,c.user_data["full_name"],c.user_data["phone"],value,user.username or "")
    c.user_data.clear()
    await u.effective_message.reply_text(f"درخواست #{rid} ثبت شد و در انتظار بررسی مدیر است. با تأیید، اطلاعات تماس در موضوع پروژه‌ها منتشر می‌شود.")
    if cfg.owner_id:
        try: await c.bot.send_message(cfg.owner_id,f"درخواست همکاری جدید #{rid}؛ برای بررسی /collabs در گروه سپس /approve {rid} یا /reject {rid}.")
        except TelegramError: pass
    return ConversationHandler.END
async def cancel(u,c): c.user_data.clear(); await u.effective_message.reply_text("لغو شد."); return ConversationHandler.END

async def enforce_violation(update,context,cfg,db,engine,rule,details,topic):
    m=update.effective_message; user=update.effective_user
    if not m or not user: return
    try: await m.delete()
    except TelegramError as e: await db.log_admin_event("delete_failed",f"chat={m.chat_id} message={m.message_id} type={type(e).__name__}")
    # مدیران/مالک: گزارش بدون تنبیه خودکار (پیش‌فرض امن)
    admin=False
    try: admin=(await context.bot.get_chat_member(m.chat_id,user.id)).status in ("administrator","creator")
    except TelegramError: pass
    update_id=str(update.update_id)
    penalty=await engine.record_violation(user.id,update_id,rule,message_kind(m),m.chat_id,m.message_id,details)
    if not penalty: return
    if admin:
        await db.log_admin_event("admin_violation",f"user={user.id} rule={rule}; no automatic penalty")
        return
    success=True
    try:
        if penalty.action in ("mute24","mute7"):
            await context.bot.restrict_chat_member(m.chat_id,user.id,permissions=ChatPermissions(**penalty.permissions),until_date=penalty.until)
        elif penalty.action=="ban":
            await context.bot.ban_chat_member(m.chat_id,user.id)
    except TelegramError as e:
        success=False; await db.log_admin_event("failed_action",f"user={user.id} rule={rule} stage={penalty.penalty_stage} error={type(e).__name__}")
    await db.log_admin_event("action_result",f"user={user.id} rule={rule} action={penalty.action} success={success}")
    if penalty.penalty_stage==1: msg="تذکر: " + details
    elif success and penalty.action.startswith("mute"): msg="به‌علت تخلف، محدودیت زمانی اعمال شد."
    elif success and penalty.action=="ban": msg="به‌علت تکرار تخلف، عضو مسدود شد."
    else: msg="تخلف ثبت شد؛ اجرای اقدام مدیریتی ناموفق بود و مدیر مطلع شده است."
    try: await context.bot.send_message(m.chat_id,msg,message_thread_id=getattr(m,"message_thread_id",None))
    except TelegramError: pass

async def on_message(u,c):
    m=u.effective_message; user=u.effective_user
    if not m or not user or m.chat.type not in (ChatType.GROUP,ChatType.SUPERGROUP): return
    cfg,db=ctx_objects(c); await db.upsert_user(user.id,user.username,user.first_name)
    admin=await is_admin(u,c,cfg)
    engine=c.application.bot_data["engine"]
    key=topic_key(m,cfg)
    # ۱) واژه‌های ممنوعه FIRST — برای هر پیام غیرمدیریتی (متن یا کپشن)، حتی اگر موضوع هنوز شناسایی نشده باشد.
    if not admin:
        banned_hit = engine.banned.find(m.text or m.caption or "")
        if banned_hit:
            return await enforce_violation(u,c,cfg,db,engine,"banned_word",
                "استفاده از واژه ممنوعه؛ پیام حذف شد.",key)
    if key is None:
        # اطلاع «موضوعات تنظیم نشده» فقط یک‌بار در طول عمر پروسه ارسال می‌شود؛ هرگز اسپم نکن.
        if not any(cfg.topics.values()) and not c.application.bot_data.get("_topics_missing_notified"):
            c.application.bot_data["_topics_missing_notified"]=True
            try: await m.reply_text("شناسه‌های موضوع تنظیم نشده‌اند. مدیر: در هر موضوع /topic_id بزنید و TOPIC_1..TOPIC_9 را در Render ثبت کنید.")
            except TelegramError: pass
        return
    # تنها مالک می‌تواند در قوانین منتشر کند؛ فقط مدیران در پروژه‌ها.
    if key=="rules" and user.id!=cfg.owner_id:
        return await enforce_violation(u,c,cfg,db,engine,"rules_only_owner","فقط مالک در قوانین و اطلاعیه‌ها پیام می‌فرستد.",key)
    if key=="projects" and not admin:
        try: await m.reply_text("ارسال مستقیم پروژه برای اعضا بسته است. برای درخواست همکاری، ربات را خصوصی شروع کنید و /collab بزنید.")
        except TelegramError: pass
        return
    # بررسی لینک/فوروارد و الفاظ
    text=m.text or m.caption or ""
    result=await engine.detect(text, list(m.entities or [])+list(m.caption_entities or []), bool(m.forward_origin),m.forward_origin)
    if result: return await enforce_violation(u,c,cfg,db,engine,result[0],result[1],key)
    # fingerprint در تمام موضوعات، برای جلوگیری از بازنشر بین موضوع‌ها
    ids=file_ids(m); fp=engine.make_fingerprint
    # coroutine fingerprint: خالی/تکراری
    is_new=await engine.make_fingerprint(text,ids,user.id,m.chat_id,m.message_id,key)
    if not is_new: return await enforce_violation(u,c,cfg,db,engine,"repeat","محتوای یکسان قبلاً ثبت شده است.",key)
    if admin: return
    now=dt.datetime.now(dt.timezone.utc)
    if key=="portfolio":
        allowed,when=await db.add_portfolio_post(user.id,m.message_id)
        if not allowed: return await m.reply_text("سهمیه نمونه‌کار پر شده است: حداکثر ۱ پست در ۷ روز و ۳ پست در ماه تقویمی. پیام جایگزین هم شمرده می‌شود.")
    elif key=="intro":
        if not await db.add_intro_post(user.id,m.message_id): return await m.reply_text("در این ماه یک معرفی مجاز است؛ اطلاعات را با ویرایش همان پیام به‌روز کنید.")
    elif key=="tariff":
        # حذف و ارسال مجدد توسط API به‌طور قطعی قابل پیوند نیست؛ نگهداری رکورد کاربر مانع دورزدن متداول است.
        tariff=await db.get_tariff(user.id); h=fingerprint(normalize_text(text),"|".join(ids) if ids else None)
        if not tariff: await db.register_tariff(user.id,m.message_id,h)
        else: await m.reply_text("تعرفه‌ی قبلی ثبت است؛ برای ویرایش همان پیام را ویرایش کنید. Telegram API امکان قفل‌کردن ویرایش کاربر را نمی‌دهد.")
    elif key=="general":
        # سقف سختِ گفت‌وگوی عمومی برای کاربران معمولی:
        # ساعتی = RATE_LIMIT_GENERAL_PER_HOUR (پیش‌فرض ۱۰) و روزانه = GENERAL_DAILY_LIMIT (پیش‌فرض ۱۵).
        now_utc=dt.datetime.now(dt.timezone.utc)
        hk=now_utc.strftime("%Y-%m-%d-%H")
        dk=now_utc.strftime("%Y-%m-%d")
        allowed=await db.bump_counter(user.id,"general","hour",hk,cfg.general_rate_limit)
        if not allowed:
            return await enforce_violation(u,c,cfg,db,engine,"general_rate_limit",
                f"بیش از حد مجاز پیام در گفت‌وگوی عمومی ({cfg.general_rate_limit} پیام در ساعت)؛ پیام حذف شد.",key)
        allowed=await db.bump_counter(user.id,"general","day",dk,cfg.general_daily_limit)
        if not allowed:
            return await enforce_violation(u,c,cfg,db,engine,"general_daily_limit",
                f"سقف روزانه گفت‌وگوی عمومی پر شد ({cfg.general_daily_limit} پیام در روز)؛ پیام حذف شد.",key)
    elif key=="podcast":
        await db.podcast_refresh_seen_other(user.id)
        allowed,why=await db.podcast_quota_check(user.id)
        if not allowed: return await m.reply_text("سهمیه پادکست پر است: ۳ پست در ساعت (با تجدیدهای مجاز) و حداکثر ۱۲ پست ثبت‌شده.")
        if not await db.was_notified(user.id,key,"limits"):
            await db.mark_notified(user.id,key,"limits"); await m.reply_text("یادآوری: سهمیه پادکست ۳ پست در ساعت، پس از ۵ کاربر متمایز دیگر یک پست اضافه، سقف کل ۱۲ است.")
