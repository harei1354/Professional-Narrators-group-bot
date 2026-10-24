import os
from dotenv import load_dotenv

load_dotenv()

GROUP_ID = int(os.getenv("GROUP_ID", "-1002345678901"))  # آیدی عددی گروه

# مپینگ تاپیک‌ها
TOPIC_GENERAL = int(os.getenv("TOPIC_1", os.getenv("TOPIC_GENERAL", "1")))
TOPIC_PODCAST = int(os.getenv("TOPIC_2", os.getenv("TOPIC_PODCAST", "213")))
TOPIC_RULES = int(os.getenv("TOPIC_3", os.getenv("TOPIC_RULES", "14")))
TOPIC_PORTFOLIO = int(os.getenv("TOPIC_4", os.getenv("TOPIC_PORTFOLIO", "3")))
TOPIC_INTRO = int(os.getenv("TOPIC_5", os.getenv("TOPIC_INTRO", "66")))
TOPIC_TARIFF = int(os.getenv("TOPIC_6", os.getenv("TOPIC_TARIFF", "72")))
TOPIC_PROJECTS = int(os.getenv("TOPIC_7", os.getenv("TOPIC_PROJECTS", "4")))
TOPIC_REVIEWS = int(os.getenv("TOPIC_8", os.getenv("TOPIC_REVIEWS", "473")))
TOPIC_AUDIO = int(os.getenv("TOPIC_9", os.getenv("TOPIC_AUDIO", "488")))

# محدودیت‌های گفتگو عمومی
GENERAL_HOURLY_LIMIT = int(os.getenv("GENERAL_HOURLY_LIMIT", "10"))
GENERAL_DAILY_LIMIT = int(os.getenv("GENERAL_DAILY_LIMIT", "15"))
MAX_WARNINGS = int(os.getenv("MAX_WARNINGS", "3"))
