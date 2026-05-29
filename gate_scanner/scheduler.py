"""
scheduler.py
=============
Automated daily post-market scheduler for the GATE Scanner.

NSE market closes at 3:30 PM IST. The default job fires at 4:00 PM IST
(Monday–Friday) to allow time for EOD data to be published by yfinance.

Usage
-----
    python -m gate_scanner.scheduler               # start blocking scheduler
    python -m gate_scanner.scheduler --time 16:30  # custom time (IST)

Requirements
------------
    pip install apscheduler

Fallback (if apscheduler not installed)
----------------------------------------
The module prints the equivalent cron expression and exits gracefully.
"""

from __future__ import annotations

import argparse
import logging

logger = logging.getLogger("gate_scanner.scheduler")

_CRON_HELP = (
    "\nAdd to your system crontab (runs Mon–Fri at 4:00 PM IST / 10:30 UTC):\n\n"
    "    30 10 * * 1-5  python -m gate_scanner.daily_scanner\n\n"
    "Or set TZ=Asia/Kolkata and run:\n\n"
    "    0 16 * * 1-5   python -m gate_scanner.daily_scanner\n"
)


def _get_scheduler_job(out_dir: str, workers: int, fno_only: bool):
    from .daily_scanner import run_daily_scan

    def _job():
        logger.info("Scheduled daily scan starting...")
        try:
            results = run_daily_scan(
                out_dir=out_dir,
                workers=workers,
                include_fno_only=fno_only,
            )
            logger.info("Scheduled scan complete: %d results", len(results))
        except Exception as exc:
            logger.exception("Scheduled scan failed: %s", exc)

    return _job


def schedule_daily(
    run_hour: int = 16,
    run_minute: int = 0,
    timezone: str = "Asia/Kolkata",
    out_dir: str = "./gate_output/daily",
    workers: int = 8,
    fno_only: bool = False,
) -> None:
    """
    Start a blocking scheduler that runs the GATE daily scan on weekdays.

    Parameters
    ----------
    run_hour   : Hour (24h) in `timezone` to run (default 16 = 4 PM IST)
    run_minute : Minute to run (default 0)
    timezone   : Timezone string (default "Asia/Kolkata")
    out_dir    : Output directory for daily scan results
    workers    : Parallel fetch workers
    fno_only   : Restrict to F&O stocks only
    """
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("apscheduler not installed.")
        print(_CRON_HELP)
        print("Install with:  pip install apscheduler>=3.10")
        return

    scheduler = BlockingScheduler(timezone=timezone)
    job = _get_scheduler_job(out_dir=out_dir, workers=workers, fno_only=fno_only)

    scheduler.add_job(
        job,
        trigger=CronTrigger(
            hour=run_hour,
            minute=run_minute,
            day_of_week="mon-fri",
            timezone=timezone,
        ),
        id="gate_daily_scan",
        name="GATE Daily Scanner",
        replace_existing=True,
    )

    run_time = f"{run_hour:02d}:{run_minute:02d} {timezone}"
    logger.info("Scheduler started — GATE daily scan will run Mon–Fri at %s", run_time)
    print(f"Scheduler active. GATE daily scan runs Mon–Fri at {run_time}.")
    print("Press Ctrl+C to stop.\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _cli():
    parser = argparse.ArgumentParser(
        description="GATE Scanner — automated daily scheduler"
    )
    parser.add_argument("--time", default="16:00",
                        help="Run time in HH:MM (IST, 24h). Default: 16:00")
    parser.add_argument("--timezone", default="Asia/Kolkata")
    parser.add_argument("--out", default="./gate_output/daily")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--fno-only", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    h, m = (int(x) for x in args.time.split(":"))
    schedule_daily(
        run_hour=h,
        run_minute=m,
        timezone=args.timezone,
        out_dir=args.out,
        workers=args.workers,
        fno_only=args.fno_only,
    )


if __name__ == "__main__":
    _cli()
