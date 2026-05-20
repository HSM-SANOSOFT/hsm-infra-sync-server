from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from hsm_sync.adapters.rsync_adapter import RsyncAdapter, _parse_bytes

SOURCE = Path("/var/www/httdocs")
KEY = Path("/home/deploy/.ssh/id_rsa")


def _adapter(**overrides) -> RsyncAdapter:
    defaults = dict(
        source_path=SOURCE,
        remote_host="192.168.1.100",
        remote_user="deploy",
        remote_path="/var/www/httdocs",
        ssh_key_path=KEY,
    )
    defaults.update(overrides)
    return RsyncAdapter(**defaults)


def _completed(stdout="", returncode=0) -> CompletedProcess:
    return CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


class TestRsyncAdapterCommand:
    def test_required_flags_present(self):
        cmd = _adapter()._build_command()
        assert "--checksum" in cmd
        assert "--delete" in cmd
        assert "--stats" in cmd

    def test_ssh_e_arg_contains_key_and_options(self):
        cmd = _adapter()._build_command()
        e_idx = cmd.index("-e")
        ssh_arg = cmd[e_idx + 1]
        assert f"-i {KEY}" in ssh_arg
        assert "BatchMode=yes" in ssh_arg
        assert "StrictHostKeyChecking=yes" in ssh_arg

    def test_default_excludes_all_present(self):
        cmd = _adapter()._build_command()
        expected = [".git/", ".env", ".env.*", "logs/", "__pycache__/", "*.pyc"]
        for exc in expected:
            assert f"--exclude={exc}" in cmd

    def test_extra_excludes_appended(self):
        cmd = _adapter(extra_excludes=["*.log", "*.bak"])._build_command()
        assert "--exclude=*.log" in cmd
        assert "--exclude=*.bak" in cmd

    def test_destination_format(self):
        cmd = _adapter()._build_command()
        assert f"{SOURCE}/" in cmd
        assert "deploy@192.168.1.100:/var/www/httdocs/" in cmd


class TestParseBytes:
    def test_normal_value(self):
        assert _parse_bytes("Total transferred file size: 23456 bytes") == 23456

    def test_zero_bytes(self):
        assert _parse_bytes("Total transferred file size: 0 bytes") == 0

    def test_with_thousands_separator(self):
        assert _parse_bytes("Total transferred file size: 1,234,567 bytes") == 1234567

    def test_missing_line(self):
        assert _parse_bytes("some other output\nno stats here") == 0

    def test_empty_stdout(self):
        assert _parse_bytes("") == 0


class TestRsyncAdapterSync:
    @patch("hsm_sync.adapters.rsync_adapter.subprocess.run")
    def test_returns_sync_result_with_bytes(self, mock_run):
        mock_run.return_value = _completed(
            stdout="Total transferred file size: 23456 bytes"
        )
        result = _adapter().sync(is_first_run=False)
        assert result.rsync_exit_code == 0
        assert result.bytes_transferred == 23456
        assert result.changed_files == []

    @patch("hsm_sync.adapters.rsync_adapter.subprocess.run")
    def test_non_zero_exit_no_exception(self, mock_run):
        mock_run.return_value = _completed(returncode=23)
        result = _adapter().sync(is_first_run=False)
        assert result.rsync_exit_code == 23

    @patch("hsm_sync.adapters.rsync_adapter.subprocess.run")
    def test_missing_stats_line_defaults_to_zero(self, mock_run):
        mock_run.return_value = _completed(stdout="no stats here")
        result = _adapter().sync(is_first_run=False)
        assert result.bytes_transferred == 0

    @patch("hsm_sync.adapters.rsync_adapter.subprocess.run")
    def test_is_first_run_passed_through(self, mock_run):
        mock_run.return_value = _completed()
        result = _adapter().sync(is_first_run=True)
        assert result.is_first_run is True
