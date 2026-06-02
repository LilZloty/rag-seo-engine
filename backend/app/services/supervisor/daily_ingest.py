"""
Daily news ingestion trigger.

Mirrors the existing `app/scheduler.py` pattern: hits the FastAPI endpoint
so the running app handles DB session, summarization, and logging in one
place. Add to crontab or Windows Task Scheduler.

Usage:
    # Run once manually
    python -m app.services.supervisor.daily_ingest

    # Linux/macOS crontab — every day at 09:00 America/Mexico_City
    0 9 * * * cd /path/to/backend && /path/to/python -m app.services.supervisor.daily_ingest

    # Windows Task Scheduler
    Program: python
    Arguments: -m app.services.supervisor.daily_ingest
    Start in: C:\\path\\to\\backend
    Trigger: Daily 9:00 AM
"""
import os
import sys
from datetime import datetime

import requests

API_BASE = os.environ.get("SUPERVISOR_API_BASE", "http://localhost:8000/api/v1/supervisor")
TIMEOUT_SECONDS = 600  # ingestion can take a minute or two when many sources are summarized


def run_ingest() -> bool:
    print(f"[{datetime.now().isoformat()}] supervisor: starting daily news ingest")
    try:
        resp = requests.post(f"{API_BASE}/news/ingest", params={"summarize": "true"}, timeout=TIMEOUT_SECONDS)
        if resp.status_code != 200:
            print(f"[supervisor] ingest failed: HTTP {resp.status_code}")
            print(f"[supervisor] body: {resp.text[:500]}")
            return False

        data = resp.json()
        print(
            f"[supervisor] ok: run_id={data.get('run_id')} "
            f"new_items={data.get('new_items')} summarized={data.get('summarized')} "
            f"errors={len(data.get('fetch_errors') or [])} "
            f"duration={data.get('duration_seconds'):.1f}s"
        )
        if data.get("fetch_errors"):
            for err in data["fetch_errors"]:
                print(f"[supervisor]   warn: {err}")
        return True
    except requests.RequestException as e:
        print(f"[supervisor] ingest error: {e}")
        return False


if __name__ == "__main__":
    sys.exit(0 if run_ingest() else 1)
