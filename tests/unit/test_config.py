from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from hsm_sync.config import load_config

_BASE_ENV = {
    "HOST_FOLDER_TO_SYNC_PATH": "/var/www/httdocs",
    "REMOTE_HOST": "192.168.1.100",
    "REMOTE_USER": "deploy",
    "REMOTE_FOLDER_TO_SYNC_PATH": "/var/www/httdocs",
    "SSH_PRIVATE_KEY_PATH": "/home/deploy/.ssh/id_rsa",
    "REMOTE_LOG_PATH": "/home/deploy/hsm-sync.log",
}


def _with_env(**overrides):
    env = {**_BASE_ENV, **overrides}
    return patch.dict(os.environ, env, clear=True)


class TestLoadConfig:
    def test_all_required_vars_set(self):
        with _with_env():
            config = load_config()
        assert config.host_folder_to_sync_path == Path("/var/www/httdocs")
        assert config.remote_host == "192.168.1.100"
        assert config.remote_user == "deploy"
        assert config.remote_folder_to_sync_path == "/var/www/httdocs"
        assert config.ssh_private_key_path == Path("/home/deploy/.ssh/id_rsa")
        assert config.remote_log_path == "/home/deploy/hsm-sync.log"

    def test_missing_remote_host_raises(self):
        env = {k: v for k, v in _BASE_ENV.items() if k != "REMOTE_HOST"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="Missing required env var: REMOTE_HOST"):
                load_config()

    def test_missing_host_folder_raises(self):
        env = {k: v for k, v in _BASE_ENV.items() if k != "HOST_FOLDER_TO_SYNC_PATH"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(
                ValueError, match="Missing required env var: HOST_FOLDER_TO_SYNC_PATH"
            ):
                load_config()

    def test_log_retention_days_default_is_7(self):
        with _with_env():
            config = load_config()
        assert config.log_retention_days == 7

    def test_rsync_excludes_parsed(self):
        with _with_env(RSYNC_EXCLUDES="*.log,*.bak"):
            config = load_config()
        assert config.rsync_excludes == ["*.log", "*.bak"]

    def test_rsync_excludes_empty_string_is_empty_list(self):
        with _with_env(RSYNC_EXCLUDES=""):
            config = load_config()
        assert config.rsync_excludes == []

    def test_ssh_private_key_path_nonexistent_loads_without_error(self):
        with _with_env(SSH_PRIVATE_KEY_PATH="/nonexistent/path/id_rsa"):
            config = load_config()
        assert config.ssh_private_key_path == Path("/nonexistent/path/id_rsa")

    def test_host_log_path_default(self):
        with _with_env():
            config = load_config()
        assert config.host_log_path == Path("logs/sync.log")

    def test_state_file_defaults_adjacent_to_log_parent(self):
        with _with_env(HOST_LOG_PATH="logs/sync.log"):
            config = load_config()
        assert config.state_file_path.name == ".hsm-sync-state"
        assert config.state_file_path.parent == config.host_log_path.parent

    def test_state_file_overridden_by_env(self):
        with _with_env(STATE_FILE_PATH="/custom/state"):
            config = load_config()
        assert config.state_file_path == Path("/custom/state")
