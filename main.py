# -*- coding: utf-8 -*-
"""main.py — راه‌اندازی Telegram bot. Render: webhook با PORT؛ توسعه: polling."""
import logging, os, sys
from telegram.ext import (Application, AIORateLimiter, CommandHandler, MessageHandler,
                          ConversationHandler, filters)
from config import load_config, ConfigError
from database import Database
from moderation import ModerationEngine, BannedWords
from handlers import *

logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"),format="%(asctime)s %(levelname)s %(name)s %(message)s")
log=logging.getLogger("narrators-bot")

def create_app(cfg, db):
    app=Application.builder().token(cfg.bot_token).rate_limiter(AIORateLimiter()).build()
    app.bot_data.update(cfg=cfg,db=db,engine=ModerationEngine(db,BannedWords(cfg.banned_words_path), owner_id=cfg.owner_id, owner_ids=getattr(cfg,'owner_ids',())))
    conv=ConversationHandler(entry_points=[CommandHandler("collab",collab_start)],
      states={FULL:[MessageHandler(filters.TEXT & ~filters.COMMAND,full_name)],PHONE:[MessageHandler(filters.TEXT & ~filters.COMMAND,phone)],EMAIL:[MessageHandler(filters.TEXT & ~filters.COMMAND,email)]},
      fallbacks=[CommandHandler("cancel",cancel)],allow_reentry=True)
    app.add_handler(CommandHandler("start",help_cmd)); app.add_handler(CommandHandler("help",help_cmd))
    app.add_handler(conv)
    for cmd,fn in [("status",status_cmd),("topic_id",topic_id),("group_id",group_id),("warnings",warnings),("history",history),("set_topic",set_topic),("unmute",unmute),("collabs",collabs),("approve",approve),("reject",reject),("backup",backup),("restore",restore),("reset_counter",reset_counter)]: app.add_handler(CommandHandler(cmd,fn))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND,on_message))
    return app

async def post_init(app):
    await app.bot.set_my_commands([]) # دستورات عمومی از /help دریافت می‌شوند.

def main():
    try: cfg=load_config()
    except ConfigError as e: log.critical("پیکربندی ناقص/نامعتبر: %s",e); sys.exit(2)
    db=Database(cfg.db_path)
    import asyncio
    asyncio.run(db.init())
    app=create_app(cfg,db)
    port=os.getenv("PORT")
    if port:
        # Render Web Service: webhook HTTPS؛ webhook path از secret path مشتق نشده و token در URL Bot API است.
        path=os.getenv("WEBHOOK_PATH","telegram-webhook")
        url=os.getenv("WEBHOOK_URL","").rstrip("/")
        if not url:
            log.critical("WEBHOOK_URL در Render باید برابر https://<نام-سرویس>.onrender.com باشد."); sys.exit(2)
        app.run_webhook(listen="0.0.0.0",port=int(port),url_path=path,webhook_url=f"{url}/{path}",secret_token=os.getenv("WEBHOOK_SECRET") or None,allowed_updates=None,drop_pending_updates=False)
    else:
        # فقط یک polling worker مجاز باشد؛ Render با PORT به webhook می‌رود.
        app.run_polling(allowed_updates=None,drop_pending_updates=False)

if __name__=="__main__": main()
