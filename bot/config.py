from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DB_PATH = Path(os.getenv("DB_PATH", ROOT_DIR / "data" / "appeals.db"))
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", "3"))
OVERDUE_DAYS = int(os.getenv("OVERDUE_DAYS", "7"))
DIGEST_DAY = int(os.getenv("DIGEST_DAY", "1"))
DIGEST_HOUR = int(os.getenv("DIGEST_HOUR", "10"))
JOBS_INTERVAL_SEC = int(os.getenv("JOBS_INTERVAL_SEC", "3600"))

# polling (локально) | webhook (Render)
MODE = os.getenv("MODE", "polling").strip().lower()

# Render задає PORT сам
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "0.0.0.0").strip()
WEBAPP_PORT = int(os.getenv("PORT") or os.getenv("WEBAPP_PORT") or "8080")

# Публічний HTTPS URL сервісу, наприклад https://kmmr-bot.onrender.com
# На Render можна не задавати вручну — є RENDER_EXTERNAL_URL
WEBHOOK_BASE_URL = (
    os.getenv("WEBHOOK_BASE_URL")
    or os.getenv("RENDER_EXTERNAL_URL")
    or ""
).rstrip("/")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook").strip() or "/webhook"
if not WEBHOOK_PATH.startswith("/"):
    WEBHOOK_PATH = "/" + WEBHOOK_PATH
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

_raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: set[int] = {
    int(item.strip())
    for item in _raw_admins.split(",")
    if item.strip().isdigit()
}


def webhook_url() -> str:
    return f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"


def require_config() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "Не задано BOT_TOKEN. Скопіюй .env.example у .env і встав токен від @BotFather."
        )
    if not ADMIN_IDS:
        raise RuntimeError(
            "Не задано ADMIN_IDS. Додай свій Telegram ID у .env (можна кілька через кому)."
        )


def require_webhook_config() -> None:
    require_config()
    if not WEBHOOK_BASE_URL:
        raise RuntimeError(
            "Для webhook задай WEBHOOK_BASE_URL, напр. https://your-app.onrender.com"
        )
    if not WEBHOOK_BASE_URL.startswith("https://"):
        raise RuntimeError("WEBHOOK_BASE_URL має бути https:// (вимога Telegram).")
    if not WEBHOOK_SECRET or len(WEBHOOK_SECRET) < 8:
        raise RuntimeError(
            "Задай WEBHOOK_SECRET (випадковий рядок від 8 символів) для захисту webhook."
        )
