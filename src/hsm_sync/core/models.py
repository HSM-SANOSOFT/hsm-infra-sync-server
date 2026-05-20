from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class FileChange:
    path: str
    status: str  # M, A, D, R


@dataclass(frozen=True)
class SyncResult:
    changed_files: list[FileChange]
    rsync_exit_code: int
    bytes_transferred: int
    is_first_run: bool


@dataclass(frozen=True)
class LogEntry:
    timestamp: datetime
    sync_result: SyncResult
