from __future__ import annotations

from datetime import UTC, datetime

from hsm_sync.core.models import LogEntry
from hsm_sync.core.ports import GitPort, LogPort, TransferPort


class SyncService:
    def __init__(
        self,
        git: GitPort,
        transfer: TransferPort,
        a_log: LogPort,
        b_log: LogPort,
    ) -> None:
        self._git = git
        self._transfer = transfer
        self._a_log = a_log
        self._b_log = b_log

    def sync(self, is_first_run: bool) -> LogEntry:
        timestamp = datetime.now(tz=UTC)
        self._git.commit(f"sync: {timestamp.isoformat()}")
        changed_files = self._git.get_changed_files()
        sync_result = self._transfer.sync(is_first_run=is_first_run)
        # Attach the git diff to the transfer result
        result = sync_result.__class__(
            changed_files=changed_files,
            rsync_exit_code=sync_result.rsync_exit_code,
            bytes_transferred=sync_result.bytes_transferred,
            is_first_run=sync_result.is_first_run,
        )
        entry = LogEntry(timestamp=timestamp, sync_result=result)
        self._a_log.write_entry(entry)
        self._b_log.write_entry(entry)
        self._a_log.prune_old_entries()
        return entry
