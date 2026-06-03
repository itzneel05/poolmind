"""
poolmind scheduler — automated maintenance tasks.
Can be run periodically via cron / Task Scheduler / systemd timer.

Usage:
    python scripts/scheduler.py              # Run all tasks once
    python scripts/scheduler.py --watch      # Run in loop every N hours
    python scripts/scheduler.py --dead-only  # Only dead link check
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper()),
    format="%(asctime)s [%(levelname)s] scheduler: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_all(auto_tombstone: bool = False):
    from app import db
    from app.audit import dead_check, get_low_confidence_resources

    logger.info("Starting scheduled maintenance...")

    dead = dead_check(limit=100, auto_tombstone=auto_tombstone)
    logger.info(
        "Dead check: %d checked, %d alive, %d dead, %d tombstoned, %d skipped",
        dead["checked"],
        dead["alive"],
        len(dead["dead"]),
        len(dead["tombstoned"]),
        dead["skipped"],
    )

    config = db.get_pool_config()
    if config.get("auto_purge_enabled") == "true":
        auto_purge_days = int(config.get("auto_purge_days", "30"))
        result = db.purge_expired_trash()
        if result["purged"] > 0:
            logger.info("Auto-purge: removed %d expired items", result["purged"])

    low_conf = get_low_confidence_resources(threshold=70)
    if low_conf:
        logger.warning(
            "%d resources with low AI confidence (need review)",
            len(low_conf),
        )

    if dead["dead"]:
        for d in dead["dead"]:
            logger.warning("Dead link: [%s] %s - %s", d["id"], d["title"], d["url"])

    logger.info("Scheduled maintenance complete.")


def watch_loop(interval_hours: int = 24, auto_tombstone: bool = False):
    logger.info(
        "Starting watch loop (interval: %d hours, auto-tombstone: %s)",
        interval_hours,
        auto_tombstone,
    )
    while True:
        run_all(auto_tombstone=auto_tombstone)
        next_run = time.time() + interval_hours * 3600
        logger.info(
            "Next run at %s",
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(next_run)),
        )
        time.sleep(interval_hours * 3600)


def main():
    parser = argparse.ArgumentParser(description="poolmind scheduler")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Run in continuous loop (default: run once and exit)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=24,
        help="Hours between runs in watch mode (default: 24)",
    )
    parser.add_argument(
        "--dead-only",
        action="store_true",
        help="Only run dead link check (skip other tasks)",
    )
    parser.add_argument(
        "--auto-tombstone",
        action="store_true",
        help="Auto-archive confirmed dead resources",
    )
    args = parser.parse_args()

    if args.dead_only:
        from app.audit import dead_check

        dead = dead_check(limit=100, auto_tombstone=args.auto_tombstone)
        print(
            f"Checked: {dead['checked']}, Alive: {dead['alive']}, "
            f"Dead: {len(dead['dead'])}, Tombstoned: {len(dead['tombstoned'])}"
        )
        return

    if args.watch:
        watch_loop(interval_hours=args.interval, auto_tombstone=args.auto_tombstone)
    else:
        run_all(auto_tombstone=args.auto_tombstone)


if __name__ == "__main__":
    main()
