from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import paramiko
import pytest

from hsm_sync.adapters.file_log_adapter import FileLogAdapter
from hsm_sync.adapters.ssh_log_adapter import SshLogAdapter
from hsm_sync.core.models import FileChange, LogEntry, SyncResult

KEY = Path("C:/Users/deploy/.ssh/id_rsa")


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


def _make_ssh_mock(exit_code: int = 0) -> MagicMock:
    """Return a mock SSHClient whose exec_command reports exit_code."""
    client = MagicMock()
    stdin = MagicMock()
    stdout = MagicMock()
    stdout.channel.recv_exit_status.return_value = exit_code
    client.exec_command.return_value = (stdin, stdout, MagicMock())
    return client


class TestSshLogAdapter:
    def _adapter(self) -> SshLogAdapter:
        return SshLogAdapter(
            host="192.168.1.100",
            user="deploy",
            key_path=KEY,
            remote_log_path=r"C:\Users\deploy\hsm-sync.log",
        )

    @patch("hsm_sync.adapters.ssh_log_adapter.paramiko.SSHClient")
    def test_uses_reject_policy(self, mock_cls):
        mock_cls.return_value = _make_ssh_mock()
        self._adapter().write_entry(_make_entry())
        policy = mock_cls.return_value.set_missing_host_key_policy.call_args[0][0]
        assert isinstance(policy, paramiko.RejectPolicy)

    @patch("hsm_sync.adapters.ssh_log_adapter.paramiko.SSHClient")
    def test_connects_with_key_no_agent(self, mock_cls):
        mock_cls.return_value = _make_ssh_mock()
        self._adapter().write_entry(_make_entry())
        kw = mock_cls.return_value.connect.call_args[1]
        assert kw["key_filename"] == str(KEY)
        assert kw["look_for_keys"] is False
        assert kw["allow_agent"] is False

    @patch("hsm_sync.adapters.ssh_log_adapter.paramiko.SSHClient")
    def test_remote_command_appends_to_path(self, mock_cls):
        mock_cls.return_value = _make_ssh_mock()
        self._adapter().write_entry(_make_entry())
        cmd = mock_cls.return_value.exec_command.call_args[0][0]
        assert "type CON >>" in cmd
        assert r"C:\Users\deploy\hsm-sync.log" in cmd

    @patch("hsm_sync.adapters.ssh_log_adapter.paramiko.SSHClient")
    def test_json_written_to_stdin(self, mock_cls):
        client = _make_ssh_mock()
        mock_cls.return_value = client
        self._adapter().write_entry(_make_entry())
        written = client.exec_command.return_value[0].write.call_args[0][0]
        json.loads(written.strip())  # Must be valid JSON

    @patch("hsm_sync.adapters.ssh_log_adapter.paramiko.SSHClient")
    def test_ssh_exception_no_raise(self, mock_cls):
        mock_cls.return_value.connect.side_effect = paramiko.SSHException("refused")
        self._adapter().write_entry(_make_entry())  # Should not raise

    @patch("hsm_sync.adapters.ssh_log_adapter.paramiko.SSHClient")
    def test_nonzero_exit_no_raise(self, mock_cls):
        mock_cls.return_value = _make_ssh_mock(exit_code=1)
        self._adapter().write_entry(_make_entry())  # Should not raise

    @patch("hsm_sync.adapters.ssh_log_adapter.paramiko.SSHClient")
    def test_prune_makes_no_connection(self, mock_cls):
        self._adapter().prune_old_entries()
        mock_cls.assert_not_called()
