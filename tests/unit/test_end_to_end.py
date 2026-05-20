from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from hsm_sync.core.models import FileChange, LogEntry, SyncResult
from hsm_sync.core.sync_service import SyncService


class MockGitAdapter:
    def __init__(self, changed_files=None):
        self._changed_files = changed_files or []
        self.commit_calls: list[str] = []
        self.get_changed_files_calls = 0

    def commit(self, message: str) -> None:
        self.commit_calls.append(message)

    def get_changed_files(self) -> list[FileChange]:
        self.get_changed_files_calls += 1
        return self._changed_files


class MockTransferAdapter:
    def __init__(self, result=None, raise_exc=None):
        self._result = result or SyncResult(
            changed_files=[],
            rsync_exit_code=0,
            bytes_transferred=0,
            is_first_run=False,
        )
        self._raise = raise_exc
        self.sync_calls: list[bool] = []

    def sync(self, is_first_run: bool) -> SyncResult:
        self.sync_calls.append(is_first_run)
        if self._raise:
            raise self._raise
        return SyncResult(
            changed_files=self._result.changed_files,
            rsync_exit_code=self._result.rsync_exit_code,
            bytes_transferred=self._result.bytes_transferred,
            is_first_run=is_first_run,
        )


class MockLogAdapter:
    def __init__(self):
        self.written: list[LogEntry] = []
        self.prune_calls = 0

    def write_entry(self, entry: LogEntry) -> None:
        self.written.append(entry)

    def prune_old_entries(self) -> None:
        self.prune_calls += 1


def _make_service(
    changed_files=None,
    transfer_result=None,
    transfer_exc=None,
) -> tuple[SyncService, MockGitAdapter, MockTransferAdapter, MockLogAdapter, MockLogAdapter]:
    git = MockGitAdapter(changed_files=changed_files)
    transfer = MockTransferAdapter(result=transfer_result, raise_exc=transfer_exc)
    a_log = MockLogAdapter()
    b_log = MockLogAdapter()
    service = SyncService(git=git, transfer=transfer, a_log=a_log, b_log=b_log)
    return service, git, transfer, a_log, b_log


class TestEndToEnd:
    def test_full_run_no_subprocess_calls(self):
        service, git, transfer, a_log, b_log = _make_service()
        entry = service.sync(is_first_run=False)
        assert isinstance(entry, LogEntry)
        assert len(git.commit_calls) == 1
        assert git.get_changed_files_calls == 1
        assert len(transfer.sync_calls) == 1
        assert len(a_log.written) == 1
        assert len(b_log.written) == 1

    def test_call_order(self):
        order = []
        git = MockGitAdapter()
        transfer = MockTransferAdapter()
        a_log = MockLogAdapter()
        b_log = MockLogAdapter()

        original_commit = git.commit
        original_get = git.get_changed_files
        original_sync = transfer.sync
        original_a_write = a_log.write_entry
        original_b_write = b_log.write_entry
        original_a_prune = a_log.prune_old_entries

        git.commit = lambda m: (order.append("git.commit"), original_commit(m))
        git.get_changed_files = lambda: (order.append("git.get_changed_files"), original_get())[1]
        transfer.sync = lambda **kw: (order.append("transfer.sync"), original_sync(**kw))[1]
        a_log.write_entry = lambda e: (order.append("a_log.write_entry"), original_a_write(e))
        b_log.write_entry = lambda e: (order.append("b_log.write_entry"), original_b_write(e))
        a_log.prune_old_entries = lambda: (order.append("a_log.prune_old_entries"), original_a_prune())

        service = SyncService(git=git, transfer=transfer, a_log=a_log, b_log=b_log)
        service.sync(is_first_run=False)

        assert order == [
            "git.commit",
            "git.get_changed_files",
            "transfer.sync",
            "a_log.write_entry",
            "b_log.write_entry",
            "a_log.prune_old_entries",
        ]

    def test_b_log_prune_never_called(self):
        service, git, transfer, a_log, b_log = _make_service()
        service.sync(is_first_run=False)
        assert b_log.prune_calls == 0

    def test_is_first_run_true_passed_to_transfer(self):
        service, git, transfer, a_log, b_log = _make_service()
        service.sync(is_first_run=True)
        assert transfer.sync_calls == [True]

    def test_log_entry_changed_files_match_git(self):
        files = [FileChange(path="index.php", status="M")]
        service, git, transfer, a_log, b_log = _make_service(changed_files=files)
        entry = service.sync(is_first_run=False)
        assert entry.sync_result.changed_files == files

    def test_transfer_error_propagates_log_not_written(self):
        service, git, transfer, a_log, b_log = _make_service(
            transfer_exc=RuntimeError("rsync failed")
        )
        with pytest.raises(RuntimeError, match="rsync failed"):
            service.sync(is_first_run=False)
        assert len(a_log.written) == 0
        assert len(b_log.written) == 0

    def test_empty_changed_files_sync_still_runs(self):
        service, git, transfer, a_log, b_log = _make_service(changed_files=[])
        entry = service.sync(is_first_run=False)
        assert entry.sync_result.changed_files == []
        assert len(transfer.sync_calls) == 1
