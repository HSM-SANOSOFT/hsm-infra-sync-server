from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from hsm_sync.adapters.file_log_adapter import FileLogAdapter
from hsm_sync.adapters.ssh_log_adapter import SshLogAdapter
from hsm_sync.core.models import FileChange, LogEntry, SyncResult

KEY = Path("/home/deploy/.ssh/id_rsa")


def _make_entry(days_ago: int = 0) -> LogEntry:
    ts = datetime.now(tz=timezone.utc) - timedelta(days=days_ago)
    return LogEntry(
        timestamp=ts,
        sync_result=SyncResult(
            changed_files=[FileChange(path="index.php", status="M")],
            rsync_exit_code=0,
            bytes_transferred=1024,
            is_first_run=False,
        ),
    )


def _completed(returncode=0) -> CompletedProcess:
    return CompletedProcess(args=[], returncode=returncode, stdout="", stderr="")


class TestFileLogAdapter:
    def test_write_entry_appends_valid_json_line(self, tmp_path):
        log = tmp_path / "sync.log"
        adapter = FileLogAdapter(log)
        adapter.write_entry(_make_entry())
        lines = log.read_text().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert "timestamp" in record
        assert "rsync_exit_code" in record

    def test_write_entry_multiple_calls_each_line(self, tmp_path):
        log = tmp_path / "sync.log"
        adapter = FileLogAdapter(log)
        adapter.write_entry(_make_entry())
        adapter.write_entry(_make_entry())
        lines = log.read_text().splitlines()
        assert len(lines) == 2

    def test_write_entry_creates_parent_directories(self, tmp_path):
        log = tmp_path / "deep" / "nested" / "sync.log"
        adapter = FileLogAdapter(log)
        adapter.write_entry(_make_entry())
        assert log.exists()

    def test_prune_removes_old_entries(self, tmp_path):
        log = tmp_path / "sync.log"
        adapter = FileLogAdapter(log, retention_days=7)
        # 3 recent + 2 old
        for _ in range(3):
            adapter.write_entry(_make_entry(days_ago=0))
        for _ in range(2):
            adapter.write_entry(_make_entry(days_ago=8))
        adapter.prune_old_entries()
        lines = [l for l in log.read_text().splitlines() if l.strip()]
        assert len(lines) == 3

    def test_prune_empty_file_no_error(self, tmp_path):
        log = tmp_path / "sync.log"
        log.write_text("")
        FileLogAdapter(log).prune_old_entries()

    def test_prune_absent_file_no_error(self, tmp_path):
        log = tmp_path / "sync.log"
        FileLogAdapter(log).prune_old_entries()

    def test_prune_no_tmp_sibling_after_success(self, tmp_path):
        log = tmp_path / "sync.log"
        adapter = FileLogAdapter(log)
        adapter.write_entry(_make_entry())
        adapter.prune_old_entries()
        tmp = log.with_suffix(log.suffix + ".tmp")
        assert not tmp.exists()


class TestSshLogAdapter:
    def _adapter(self) -> SshLogAdapter:
        return SshLogAdapter(
            host="192.168.1.100",
            user="deploy",
            key_path=KEY,
            remote_log_path="/home/deploy/hsm-sync.log",
        )

    @patch("hsm_sync.adapters.ssh_log_adapter.subprocess.run")
    def test_write_entry_calls_ssh_with_correct_options(self, mock_run):
        mock_run.return_value = _completed()
        self._adapter().write_entry(_make_entry())
        cmd = mock_run.call_args[0][0]
        assert "ssh" in cmd
        assert "BatchMode=yes" in cmd
        assert "StrictHostKeyChecking=yes" in cmd
        assert "deploy@192.168.1.100" in cmd

    @patch("hsm_sync.adapters.ssh_log_adapter.subprocess.run")
    def test_write_entry_appends_to_remote_path(self, mock_run):
        mock_run.return_value = _completed()
        self._adapter().write_entry(_make_entry())
        cmd = mock_run.call_args[0][0]
        remote_cmd = cmd[-1]
        assert "cat >>" in remote_cmd
        assert "/home/deploy/hsm-sync.log" in remote_cmd

    @patch("hsm_sync.adapters.ssh_log_adapter.subprocess.run")
    def test_json_passed_via_stdin_not_shell_arg(self, mock_run):
        mock_run.return_value = _completed()
        self._adapter().write_entry(_make_entry())
        kwargs = mock_run.call_args[1]
        assert "input" in kwargs
        # Content is valid JSON
        json.loads(kwargs["input"].strip())

    @patch("hsm_sync.adapters.ssh_log_adapter.subprocess.run")
    def test_ssh_failure_no_exception(self, mock_run):
        mock_run.return_value = _completed(returncode=255)
        # Should not raise
        self._adapter().write_entry(_make_entry())

    @patch("hsm_sync.adapters.ssh_log_adapter.subprocess.run")
    def test_prune_old_entries_makes_no_subprocess_call(self, mock_run):
        self._adapter().prune_old_entries()
        mock_run.assert_not_called()
