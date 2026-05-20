from __future__ import annotations

import stat as stat_mod
from pathlib import Path
from unittest.mock import MagicMock, patch

import paramiko
import pytest

from hsm_sync.adapters.sftp_adapter import (
    SftpAdapter,
    _DEFAULT_EXCLUDES,
    _is_excluded,
)

HOST = "192.168.1.100"
REMOTE = "C:/inetpub/wwwroot"
KEY = Path("C:/Users/deploy/.ssh/id_rsa")


def _sftp_attr(filename: str, size: int, is_dir: bool = False) -> MagicMock:
    a = MagicMock()
    a.filename = filename
    a.st_size = size
    a.st_mode = (stat_mod.S_IFDIR | 0o755) if is_dir else (stat_mod.S_IFREG | 0o644)
    return a


def _adapter(tmp_path: Path, **kw) -> SftpAdapter:
    return SftpAdapter(
        source_path=tmp_path,
        remote_host=HOST,
        remote_user="deploy",
        remote_path=REMOTE,
        ssh_key_path=KEY,
        **kw,
    )


def _setup_empty_remote(mock_ssh_cls: MagicMock) -> MagicMock:
    """Configure mock so remote appears empty (listdir_attr raises OSError)."""
    client = mock_ssh_cls.return_value
    sftp = client.open_sftp.return_value
    sftp.listdir_attr.side_effect = OSError("no such directory")
    sftp.stat.side_effect = OSError("no such directory")
    return sftp


def _setup_remote_with(mock_ssh_cls: MagicMock, files: dict[str, int]) -> MagicMock:
    """Configure mock so remote has given {filename: size} files at top level."""
    client = mock_ssh_cls.return_value
    sftp = client.open_sftp.return_value
    sftp.listdir_attr.return_value = [_sftp_attr(k, v) for k, v in files.items()]
    sftp.stat.side_effect = OSError
    return sftp


class TestSftpAdapterSecurity:
    @patch("hsm_sync.adapters.sftp_adapter.paramiko.SSHClient")
    def test_uses_reject_policy(self, mock_cls, tmp_path):
        _setup_empty_remote(mock_cls)
        _adapter(tmp_path).sync(is_first_run=False)
        policy = mock_cls.return_value.set_missing_host_key_policy.call_args[0][0]
        assert isinstance(policy, paramiko.RejectPolicy)

    @patch("hsm_sync.adapters.sftp_adapter.paramiko.SSHClient")
    def test_connects_with_key_no_agent(self, mock_cls, tmp_path):
        _setup_empty_remote(mock_cls)
        _adapter(tmp_path).sync(is_first_run=False)
        kw = mock_cls.return_value.connect.call_args[1]
        assert kw["key_filename"] == str(KEY)
        assert kw["look_for_keys"] is False
        assert kw["allow_agent"] is False

    @patch("hsm_sync.adapters.sftp_adapter.paramiko.SSHClient")
    def test_loads_system_host_keys(self, mock_cls, tmp_path):
        _setup_empty_remote(mock_cls)
        _adapter(tmp_path).sync(is_first_run=False)
        mock_cls.return_value.load_system_host_keys.assert_called_once()


class TestSftpAdapterSync:
    @patch("hsm_sync.adapters.sftp_adapter.paramiko.SSHClient")
    def test_uploads_new_file(self, mock_cls, tmp_path):
        (tmp_path / "index.php").write_bytes(b"<?php echo 1; ?>")
        sftp = _setup_empty_remote(mock_cls)

        result = _adapter(tmp_path).sync(is_first_run=False)

        sftp.put.assert_called_once()
        assert "index.php" in sftp.put.call_args[0][1]
        assert result.rsync_exit_code == 0

    @patch("hsm_sync.adapters.sftp_adapter.paramiko.SSHClient")
    def test_skips_file_with_same_size(self, mock_cls, tmp_path):
        content = b"<?php echo 1; ?>"
        (tmp_path / "index.php").write_bytes(content)
        _setup_remote_with(mock_cls, {"index.php": len(content)})

        result = _adapter(tmp_path).sync(is_first_run=False)

        mock_cls.return_value.open_sftp.return_value.put.assert_not_called()
        assert result.bytes_transferred == 0

    @patch("hsm_sync.adapters.sftp_adapter.paramiko.SSHClient")
    def test_uploads_file_with_different_size(self, mock_cls, tmp_path):
        (tmp_path / "index.php").write_bytes(b"updated content here")
        _setup_remote_with(mock_cls, {"index.php": 5})  # Old size was 5

        mock_cls.return_value.open_sftp.return_value.stat.side_effect = OSError
        _adapter(tmp_path).sync(is_first_run=False)

        mock_cls.return_value.open_sftp.return_value.put.assert_called_once()

    @patch("hsm_sync.adapters.sftp_adapter.paramiko.SSHClient")
    def test_deletes_file_removed_locally(self, mock_cls, tmp_path):
        # Local is empty; remote has a file that was deleted
        _setup_remote_with(mock_cls, {"stale.php": 100})

        _adapter(tmp_path).sync(is_first_run=False)

        sftp = mock_cls.return_value.open_sftp.return_value
        sftp.remove.assert_called_once_with(f"{REMOTE}/stale.php")

    @patch("hsm_sync.adapters.sftp_adapter.paramiko.SSHClient")
    def test_bytes_transferred_counts_uploads(self, mock_cls, tmp_path):
        content = b"hello world"
        (tmp_path / "index.php").write_bytes(content)
        _setup_empty_remote(mock_cls)

        result = _adapter(tmp_path).sync(is_first_run=False)

        assert result.bytes_transferred == len(content)

    @patch("hsm_sync.adapters.sftp_adapter.paramiko.SSHClient")
    def test_is_first_run_passed_through(self, mock_cls, tmp_path):
        _setup_empty_remote(mock_cls)
        result = _adapter(tmp_path).sync(is_first_run=True)
        assert result.is_first_run is True

    @patch("hsm_sync.adapters.sftp_adapter.paramiko.SSHClient")
    def test_connection_closed_after_sync(self, mock_cls, tmp_path):
        _setup_empty_remote(mock_cls)
        _adapter(tmp_path).sync(is_first_run=False)
        mock_cls.return_value.close.assert_called_once()


class TestSftpAdapterExcludes:
    def test_excludes_dot_git_directory(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_bytes(b"ref: refs/heads/main")
        (tmp_path / "index.php").write_bytes(b"<?php ?>")

        local = _adapter(tmp_path)._walk_local()

        assert "index.php" in local
        assert not any(k.startswith(".git") for k in local)

    def test_excludes_env_files(self, tmp_path):
        (tmp_path / ".env").write_bytes(b"SECRET=x")
        (tmp_path / ".env.local").write_bytes(b"DEBUG=1")
        (tmp_path / "index.php").write_bytes(b"<?php ?>")

        local = _adapter(tmp_path)._walk_local()

        assert "index.php" in local
        assert ".env" not in local
        assert ".env.local" not in local

    def test_excludes_pyc_files(self, tmp_path):
        (tmp_path / "app.pyc").write_bytes(b"bytecode")
        (tmp_path / "index.php").write_bytes(b"<?php ?>")

        local = _adapter(tmp_path)._walk_local()

        assert "index.php" in local
        assert "app.pyc" not in local

    def test_excludes_logs_directory(self, tmp_path):
        (tmp_path / "logs").mkdir()
        (tmp_path / "logs" / "sync.log").write_bytes(b"log data")
        (tmp_path / "index.php").write_bytes(b"<?php ?>")

        local = _adapter(tmp_path)._walk_local()

        assert "index.php" in local
        assert not any(k.startswith("logs") for k in local)

    def test_extra_excludes_honored(self, tmp_path):
        (tmp_path / "video.mp4").write_bytes(b"binary")
        (tmp_path / "index.php").write_bytes(b"<?php ?>")

        local = _adapter(tmp_path, extra_excludes=["*.mp4"])._walk_local()

        assert "index.php" in local
        assert "video.mp4" not in local


class TestIsExcluded:
    def test_git_dir(self):
        assert _is_excluded(".git/", _DEFAULT_EXCLUDES)

    def test_env_file(self):
        assert _is_excluded(".env", _DEFAULT_EXCLUDES)

    def test_env_variant(self):
        assert _is_excluded(".env.local", _DEFAULT_EXCLUDES)

    def test_pyc_file(self):
        assert _is_excluded("subdir/app.pyc", _DEFAULT_EXCLUDES)

    def test_logs_dir(self):
        assert _is_excluded("logs/", _DEFAULT_EXCLUDES)

    def test_file_inside_logs(self):
        assert _is_excluded("logs/sync.log", _DEFAULT_EXCLUDES)

    def test_normal_php_not_excluded(self):
        assert not _is_excluded("index.php", _DEFAULT_EXCLUDES)

    def test_normal_subdir_not_excluded(self):
        assert not _is_excluded("css/style.css", _DEFAULT_EXCLUDES)
