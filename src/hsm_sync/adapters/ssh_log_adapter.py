from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from hsm_sync.adapters.file_log_adapter import _entry_to_dict
from hsm_sync.core.models import LogEntry


class SshLogAdapter:
    def __init__(
        self,
        host: str,
        user: str,
        key_path: Path,
        remote_log_path: str,
    ) -> None:
        self._host = host
        self._user = user
        self._key = key_path
        self._remote_log_path = remote_log_path

    def write_entry(self, entry: LogEntry) -> None:
        json_line = json.dumps(_entry_to_dict(entry))
        proc = subprocess.run(
            [
                "ssh",
                "-i",
                str(self._key),
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=yes",
                f"{self._user}@{self._host}",
                f"cat >> '{self._remote_log_path}'",
            ],
            input=json_line + "\n",
            text=True,
            capture_output=True,
        )
        if proc.returncode != 0:
            msg = (
                f"WARNING: B-side log write failed"
                f" (exit {proc.returncode}): {proc.stderr.strip()}"
            )
            print(msg, file=sys.stderr)

    def prune_old_entries(self) -> None:
        pass  # B-side log is not pruned by this tool
