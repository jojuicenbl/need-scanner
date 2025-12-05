"""Scan Worker for Need Scanner.

Step 2 Architecture: Job Queue Worker
=====================================
This worker process polls the database for queued scan jobs and
processes them asynchronously. It uses FOR UPDATE SKIP LOCKED
to safely claim jobs in a concurrent environment.

Usage:
    python -m need_scanner.worker

    # With custom poll interval (default: 5 seconds)
    SCAN_WORKER_POLL_INTERVAL_SECONDS=10 python -m need_scanner.worker

    # With worker ID for logging
    SCAN_WORKER_ID=worker-1 python -m need_scanner.worker

Multiple workers can run safely in parallel - each will claim
different jobs from the queue without conflicts.

Environment Variables:
    SCAN_WORKER_POLL_INTERVAL_SECONDS: Poll interval (default: 5)
    SCAN_WORKER_ID: Worker identifier for logging (default: auto-generated)
    DATABASE_URL: PostgreSQL connection string (required)
"""

import os
import sys
import time
import signal
import traceback
from datetime import datetime
from typing import Optional, Dict
from pathlib import Path
import uuid

from loguru import logger

# Configure loguru for worker output
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>worker</cyan> | <level>{message}</level>",
    level="INFO",
)


class ScanWorker:
    """Worker process that polls for and executes scan jobs.

    Attributes:
        worker_id: Unique identifier for this worker instance
        poll_interval: Seconds to wait between polling for jobs
        running: Whether the worker should continue running
    """

    def __init__(
        self,
        worker_id: Optional[str] = None,
        poll_interval: int = 5,
    ):
        """Initialize the scan worker.

        Args:
            worker_id: Unique worker identifier (auto-generated if not provided)
            poll_interval: Seconds between job queue polls (default: 5)
        """
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.poll_interval = poll_interval
        self.running = False
        self._current_job_id: Optional[str] = None

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.warning(f"Received signal {signum}, shutting down...")
        self.running = False

        if self._current_job_id:
            logger.warning(f"Job {self._current_job_id} was in progress - it will remain in 'running' state")
            logger.warning("You may need to manually reset it or let it time out")

    def start(self):
        """Start the worker's main loop.

        This method runs indefinitely, polling for jobs and processing them.
        Use Ctrl+C or SIGTERM to stop gracefully.
        """
        # Import here to avoid circular imports and ensure DB is configured
        from .db import (
            init_database,
            claim_next_job,
            update_job_progress,
            complete_job,
            fail_job,
            save_insights,
        )
        from .core import run_scan_for_worker

        logger.info("=" * 60)
        logger.info(f"Need Scanner Worker Starting")
        logger.info(f"   Worker ID: {self.worker_id}")
        logger.info(f"   Poll Interval: {self.poll_interval}s")
        logger.info("=" * 60)

        # Initialize database connection
        try:
            init_database()
            logger.info("Database connection verified")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            sys.exit(1)

        self.running = True
        jobs_processed = 0
        jobs_failed = 0

        logger.info("Worker started. Polling for jobs...")

        while self.running:
            try:
                # Try to claim a job
                job = claim_next_job(worker_id=self.worker_id)

                if job is None:
                    # No jobs available, sleep and try again
                    time.sleep(self.poll_interval)
                    continue

                # We have a job to process
                run_id = job["id"]
                self._current_job_id = run_id

                logger.info("-" * 40)
                logger.info(f"Processing job: {run_id}")
                logger.info(f"   Mode: {job.get('mode', 'deep')}")
                logger.info(f"   Run Mode: {job.get('run_mode', 'discover')}")
                logger.info(f"   Max Insights: {job.get('max_insights', 'unlimited')}")
                logger.info("-" * 40)

                try:
                    # Create a progress callback
                    def progress_callback(progress: int, message: str = ""):
                        if self.running:  # Only update if not shutting down
                            update_job_progress(run_id, progress)
                            if message:
                                logger.info(f"   [{progress}%] {message}")

                    # Run the scan
                    result = run_scan_for_worker(
                        run_id=run_id,
                        mode=job.get("mode", "deep"),
                        run_mode=job.get("run_mode", "discover"),
                        max_insights=job.get("max_insights"),
                        input_pattern=job.get("input_pattern", "data/raw/posts_*.json"),
                        config_name=job.get("config_name"),
                        progress_callback=progress_callback,
                    )

                    # Job completed successfully
                    complete_job(
                        run_id=run_id,
                        nb_insights=result["nb_insights"],
                        nb_clusters=result["nb_clusters"],
                        total_cost_usd=result.get("total_cost_usd", 0.0),
                        embed_cost_usd=result.get("embed_cost_usd", 0.0),
                        summary_cost_usd=result.get("summary_cost_usd", 0.0),
                        csv_path=result.get("csv_path"),
                        json_path=result.get("json_path"),
                        notes=result.get("notes"),
                        run_stats=result.get("run_stats"),
                    )

                    # Save insights to database
                    if result.get("insights"):
                        save_insights(run_id=run_id, insights=result["insights"])

                    jobs_processed += 1
                    logger.info(f"Job {run_id} completed successfully")
                    logger.info(f"   Insights: {result['nb_insights']}")
                    logger.info(f"   Cost: ${result.get('total_cost_usd', 0):.4f}")

                except Exception as e:
                    # Job failed
                    error_msg = f"{type(e).__name__}: {str(e)}"
                    logger.error(f"Job {run_id} failed: {error_msg}")
                    logger.debug(traceback.format_exc())

                    fail_job(run_id, error_msg)
                    jobs_failed += 1

                finally:
                    self._current_job_id = None

            except KeyboardInterrupt:
                # This shouldn't happen since we handle SIGINT, but just in case
                logger.info("Interrupted by user")
                break

            except Exception as e:
                # Unexpected error in the main loop
                logger.error(f"Unexpected error in worker loop: {e}")
                logger.debug(traceback.format_exc())
                time.sleep(self.poll_interval)

        # Shutdown
        logger.info("=" * 60)
        logger.info("Worker shutting down")
        logger.info(f"   Jobs processed: {jobs_processed}")
        logger.info(f"   Jobs failed: {jobs_failed}")
        logger.info("=" * 60)


def main():
    """Main entry point for the scan worker."""
    # Read configuration from environment
    poll_interval = int(os.getenv("SCAN_WORKER_POLL_INTERVAL_SECONDS", "5"))
    worker_id = os.getenv("SCAN_WORKER_ID")

    # Validate poll interval
    if poll_interval < 1:
        logger.warning(f"Poll interval {poll_interval}s is too short, using 1s")
        poll_interval = 1
    elif poll_interval > 60:
        logger.warning(f"Poll interval {poll_interval}s is quite long, consider using a shorter interval")

    # Create and start the worker
    worker = ScanWorker(
        worker_id=worker_id,
        poll_interval=poll_interval,
    )
    worker.start()


if __name__ == "__main__":
    main()
