import sys

from celery import Celery
from celery.schedules import crontab
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "gate_tasks",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.scanner_tasks", "app.tasks.backtest_tasks", "app.tasks.stock_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    # billiard's prefork pool uses POSIX shared semaphores that fail on Windows;
    # solo pool runs tasks in-process and avoids the IPC entirely
    **({"worker_pool": "solo"} if sys.platform == "win32" else {}),
    # Scheduled scans: post-market Mon–Fri at 4:05 PM IST
    beat_schedule={
        "daily-post-market-scan": {
            "task": "app.tasks.scanner_tasks.run_scheduled_scan",
            "schedule": crontab(hour=16, minute=5, day_of_week="1-5"),
            "args": ([], "daily"),
        },
        # Refresh NSE equity list + index flags every Sunday at 6 AM IST
        "weekly-stock-master-sync": {
            "task": "app.tasks.stock_tasks.sync_stock_master",
            "schedule": crontab(hour=6, minute=0, day_of_week="0"),
            "args": (["equity", "index_flags"],),
        },
        # Incrementally enrich pending/failed fundamentals every 15 minutes
        "fundamentals-enrichment-batch": {
            "task": "app.tasks.stock_tasks.enrich_fundamentals_batch",
            "schedule": crontab(minute="*/15"),
        },
    },
)
