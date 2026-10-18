"""Запуск для Render / будь-якого HTTPS-хостингу (webhook)."""

from bot.webhook_app import run_webhook_sync

if __name__ == "__main__":
    run_webhook_sync()
