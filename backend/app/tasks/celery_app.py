from celery import Celery
from celery.schedules import crontab
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "gate_tasks",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.scanner_tasks", "app.tasks.backtest_tasks"],
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
    # Scheduled scans: post-market Mon–Fri at 4:05 PM IST
    beat_schedule={
        "daily-post-market-scan": {
            "task": "app.tasks.scanner_tasks.run_scheduled_scan",
            "schedule": crontab(hour=16, minute=5, day_of_week="1-5"),
            "args": ([], "daily"),
        }
    },
)
