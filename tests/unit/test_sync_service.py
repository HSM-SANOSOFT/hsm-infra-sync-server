from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from hsm_sync.core.models import FileChange, LogEntry, SyncResult
from hsm_sync.core.sync_service import SyncService


def _make_sync_result(**overrides) -> SyncResult:
    defaults = dict(
        changed_files=[],
        rsync_exit_code=0,
        bytes_transferred=0,
        is_first_run=False,
    )
    defaults.update(overrides)
    return SyncResult(**defaults)


def _make_service(
    changed_files=None,
    sync_result=None,
    is_first_run_default=False,
):
    if changed_files is None:
        changed_files = []
    if sync_result is None:
        sync_result = _make_sync_result(is_first_run=is_first_run_default)

    git = MagicMock()
    git.get_changed_files.return_value = changed_files
    transfer = MagicMock()
    transfer.sync.return_value = sync_result
    a_log = MagicMock()
    b_log = MagicMock()
    service = SyncService(git=git, transfer=transfer, a_log=a_log, b_log=b_log)
    return service, git, transfer, a_log, b_log


class TestSyncServiceHappyPath:
    def test_calls_all_ports_in_order(self):
        service, git, transfer, a_log, b_log = _make_service()
        manager = MagicMock()
        manager.attach_mock(git, "git")
        manager.attach_mock(transfer, "transfer")
        manager.attach_mock(a_log, "a_log")
        manager.attach_mock(b_log, "b_log")

        service.sync(is_first_run=False)

        calls = manager.mock_calls
        method_names = [c[0] for c in calls]
        git_commit_idx = next(i for i, n in enumerate(method_names) if n == "git.commit")
        git_diff_idx = next(i for i, n in enumerate(method_names) if n == "git.get_changed_files")
        transfer_idx = next(i for i, n in enumerate(method_names) if n == "transfer.sync")
        a_write_idx = next(i for i, n in enumerate(method_names) if n == "a_log.write_entry")
        b_write_idx = next(i for i, n in enumerate(method_names) if n == "b_log.write_entry")
        a_prune_idx = next(i for i, n in enumerate(method_names) if n == "a_log.prune_old_entries")

        assert git_commit_idx < git_diff_idx < transfer_idx < a_write_idx
        assert a_write_idx < b_write_idx < a_prune_idx

    def test_passes_is_first_run_true_to_transfer(self):
        service, git, transfer, a_log, b_log = _make_service(
            sync_result=_make_sync_result(is_first_run=True),
            is_first_run_default=True,
        )
        transfer.sync.return_value = _make_sync_result(is_first_run=True)
        service.sync(is_first_run=True)
        transfer.sync.assert_called_once_with(is_first_run=True)

    def test_returned_log_entry_contains_changed_files(self):
        files = [FileChange(path="index.php", status="M")]
        sync_result = _make_sync_result()
        service, git, transfer, a_log, b_log = _make_service(
            changed_files=files, sync_result=sync_result
        )
        entry = service.sync(is_first_run=False)
        assert isinstance(entry, LogEntry)
        assert entry.sync_result.changed_files == files

    def test_b_log_prune_not_called(self):
        service, git, transfer, a_log, b_log = _make_service()
        service.sync(is_first_run=False)
        b_log.prune_old_entries.assert_not_called()

    def test_a_log_prune_called_once(self):
        service, git, transfer, a_log, b_log = _make_service()
        service.sync(is_first_run=False)
        a_log.prune_old_entries.assert_called_once()


class TestSyncServiceErrorPath:
    def test_transfer_error_propagates_and_log_not_written(self):
        service, git, transfer, a_log, b_log = _make_service()
        transfer.sync.side_effect = RuntimeError("rsync failed")

        with pytest.raises(RuntimeError, match="rsync failed"):
            service.sync(is_first_run=False)

        a_log.write_entry.assert_not_called()
        b_log.write_entry.assert_not_called()
