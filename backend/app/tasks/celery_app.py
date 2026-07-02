import ssl
import sys

from celery import Celery
from celery.schedules import crontab
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "gate_tasks",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.scanner_tasks",
        "app.tasks.stock_tasks",
        "app.tasks.screener_tasks",
    ],
)

celery_app.conf.update(
    # Serialisation
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone
    timezone="Asia/Kolkata",
    enable_utc=True,

    # Reliability
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,

    # Don't store task results in Redis — reduces Upstash free-tier request usage.
    task_ignore_result=True,
    task_send_sent_event=False,       # disables per-task sent events via broker
    worker_send_task_events=False,    # disables worker heartbeats via broker
    # Increase BRPOP timeout: 30s blocks instead of default 5s → 86k BRPOP/month
    # vs 518k/month. Safety net for local dev (production has no worker).
    broker_transport_options={
        "socket_timeout": 30,
        "visibility_timeout": 3600,
    },

    # Task routing — separate queues per concern
    task_default_queue="default",
    task_queues={
        "scans":    {"exchange": "scans",    "routing_key": "scans"},
        "admin":    {"exchange": "admin",    "routing_key": "admin"},
        "default":  {"exchange": "default",  "routing_key": "default"},
    },
    task_routes={
        "app.tasks.scanner_tasks.run_scan_task":        {"queue": "scans"},
        "app.tasks.scanner_tasks.run_scheduled_scan":   {"queue": "scans"},
        "app.tasks.stock_tasks.sync_stock_master":      {"queue": "admin"},
        "app.tasks.stock_tasks.enrich_fundamentals_batch": {"queue": "admin"},
        "app.tasks.screener_tasks.sync_screener_fundamentals": {"queue": "admin"},
    },

    # TLS for Upstash — rediss:// requires explicit ssl_cert_reqs
    **({"broker_use_ssl": {"ssl_cert_reqs": ssl.CERT_NONE},
        "redis_backend_use_ssl": {"ssl_cert_reqs": ssl.CERT_NONE}}
       if settings.redis_url.startswith("rediss://") else {}),

    # Windows compatibility: solo pool avoids POSIX semaphore failures
    **({"worker_pool": "solo"} if sys.platform == "win32" else {}),

    # Scheduled tasks
    beat_schedule={
        "daily-post-market-scan": {
            "task": "app.tasks.scanner_tasks.run_scheduled_scan",
            "schedule": crontab(hour=16, minute=5, day_of_week="1-5"),
            "args": ([], "daily"),
            "options": {"queue": "scans"},
        },
        "weekly-screener-fundamentals-sync": {
            "task": "app.tasks.screener_tasks.sync_screener_fundamentals",
            "schedule": crontab(hour=4, minute=30, day_of_week="0"),  # 04:30 UTC Sunday
            "options": {"queue": "admin"},
        },
        "weekly-stock-master-sync": {
            "task": "app.tasks.stock_tasks.sync_stock_master",
            "schedule": crontab(hour=6, minute=0, day_of_week="0"),
            "args": (["equity", "bse_equity", "index_flags"],),
            "options": {"queue": "admin"},
        },
        "fundamentals-enrichment-batch": {
            "task": "app.tasks.stock_tasks.enrich_fundamentals_batch",
            "schedule": crontab(minute="*/15"),
            "options": {"queue": "admin"},
        },
    },
)
