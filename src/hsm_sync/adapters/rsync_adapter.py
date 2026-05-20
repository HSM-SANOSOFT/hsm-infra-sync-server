from __future__ import annotations

import re
import subprocess
from pathlib import Path

from hsm_sync.core.models import SyncResult

_DEFAULT_EXCLUDES = [".git/", ".env", ".env.*", "logs/", "__pycache__/", "*.pyc"]
_BYTES_PATTERN = re.compile(r"Total transferred file size:\s+([\d,]+)\s+bytes")


class RsyncAdapter:
    def __init__(
        self,
        source_path: Path,
        remote_host: str,
        remote_user: str,
        remote_path: str,
        ssh_key_path: Path,
        extra_excludes: list[str] | None = None,
    ) -> None:
        self._source = source_path
        self._host = remote_host
        self._user = remote_user
        self._remote_path = remote_path
        self._key = ssh_key_path
        self._extra_excludes = extra_excludes or []

    def sync(self, is_first_run: bool) -> SyncResult:
        cmd = self._build_command()
        proc = subprocess.run(cmd, capture_output=True, text=True)
        bytes_transferred = _parse_bytes(proc.stdout)
        return SyncResult(
            changed_files=[],
            rsync_exit_code=proc.returncode,
            bytes_transferred=bytes_transferred,
            is_first_run=is_first_run,
        )

    def _build_command(self) -> list[str]:
        ssh_opts = (
            f"ssh -i {self._key}"
            " -o BatchMode=yes"
            " -o StrictHostKeyChecking=yes"
        )
        excludes = [
            f"--exclude={x}" for x in (_DEFAULT_EXCLUDES + self._extra_excludes)
        ]
        return [
            "rsync",
            "-avz",
            "--checksum",
            "--delete",
            "--stats",
            "-e",
            ssh_opts,
            *excludes,
            f"{self._source}/",
            f"{self._user}@{self._host}:{self._remote_path}/",
        ]


def _parse_bytes(stdout: str) -> int:
    match = _BYTES_PATTERN.search(stdout)
    if not match:
        return 0
    return int(match.group(1).replace(",", ""))
