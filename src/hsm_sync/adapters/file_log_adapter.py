from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from hsm_sync.core.models import LogEntry


def _entry_to_dict(entry: LogEntry) -> dict:
    return {
        "timestamp": entry.timestamp.isoformat(),
        "changed_files": [
            {"path": f.path, "status": f.status}
            for f in entry.sync_result.changed_files
        ],
        "rsync_exit_code": entry.sync_result.rsync_exit_code,
        "bytes_transferred": entry.sync_result.bytes_transferred,
        "is_first_run": entry.sync_result.is_first_run,
    }


class FileLogAdapter:
    def __init__(self, log_path: Path, retention_days: int = 7) -> None:
        self._path = log_path
        self._retention_days = retention_days

    def write_entry(self, entry: LogEntry) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a") as f:
            f.write(json.dumps(_entry_to_dict(entry)) + "\n")

    def prune_old_entries(self) -> None:
        if not self._path.exists():
            return

        cutoff = datetime.now(tz=UTC) - timedelta(days=self._retention_days)
        lines = self._path.read_text().splitlines()
        kept = []
        for line in lines:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                ts = datetime.fromisoformat(record["timestamp"])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                if ts >= cutoff:
                    kept.append(line)
            except (json.JSONDecodeError, KeyError, ValueError):
                kept.append(line)  # Keep malformed lines rather than silently drop

        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text("\n".join(kept) + ("\n" if kept else ""))
        os.replace(tmp, self._path)
