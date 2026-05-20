from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class SyncConfig:
    httdocs_path: Path
    remote_host: str
    remote_user: str
    remote_path: str
    ssh_key_path: Path
    remote_log_path: str
    local_log_path: Path
    log_retention_days: int
    rsync_excludes: list[str]
    state_file_path: Path


def load_config() -> SyncConfig:
    load_dotenv()

    def _require(name: str) -> str:
        value = os.environ.get(name)
        if not value:
            raise ValueError(f"Missing required env var: {name}")
        return value

    httdocs_path = Path(_require("HTTDOCS_PATH"))
    remote_host = _require("REMOTE_HOST")
    remote_user = _require("REMOTE_USER")
    remote_path = _require("REMOTE_PATH")
    ssh_key_path = Path(_require("SSH_KEY_PATH"))
    remote_log_path = _require("REMOTE_LOG_PATH")

    local_log_path = Path(os.environ.get("LOCAL_LOG_PATH", "logs/sync.log"))
    log_retention_days = int(os.environ.get("LOG_RETENTION_DAYS", "7"))

    raw_excludes = os.environ.get("RSYNC_EXCLUDES", "")
    rsync_excludes = [x.strip() for x in raw_excludes.split(",") if x.strip()]

    default_state = local_log_path.parent / ".hsm-sync-state"
    state_file_path = Path(os.environ.get("STATE_FILE_PATH", str(default_state)))

    return SyncConfig(
        httdocs_path=httdocs_path,
        remote_host=remote_host,
        remote_user=remote_user,
        remote_path=remote_path,
        ssh_key_path=ssh_key_path,
        remote_log_path=remote_log_path,
        local_log_path=local_log_path,
        log_retention_days=log_retention_days,
        rsync_excludes=rsync_excludes,
        state_file_path=state_file_path,
    )
