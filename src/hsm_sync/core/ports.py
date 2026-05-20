from __future__ import annotations

from typing import Protocol

from hsm_sync.core.models import FileChange, LogEntry, SyncResult


class GitPort(Protocol):
    def commit(self, message: str) -> None: ...

    def get_changed_files(self) -> list[FileChange]: ...


class TransferPort(Protocol):
    def sync(self, is_first_run: bool) -> SyncResult: ...


class LogPort(Protocol):
    def write_entry(self, entry: LogEntry) -> None: ...

    def prune_old_entries(self) -> None: ...
