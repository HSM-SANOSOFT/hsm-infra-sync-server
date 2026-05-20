from __future__ import annotations

import subprocess
import sys

from hsm_sync.adapters.file_log_adapter import FileLogAdapter
from hsm_sync.adapters.git_adapter import GitAdapter
from hsm_sync.adapters.rsync_adapter import RsyncAdapter
from hsm_sync.adapters.ssh_log_adapter import SshLogAdapter
from hsm_sync.config import load_config
from hsm_sync.core.sync_service import SyncService


def main() -> None:
    try:
        config = load_config()
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    state_file = config.state_file_path
    is_first_run = not state_file.exists() or state_file.read_text().strip() == ""

    git = GitAdapter(config.httdocs_path)
    transfer = RsyncAdapter(
        source_path=config.httdocs_path,
        remote_host=config.remote_host,
        remote_user=config.remote_user,
        remote_path=config.remote_path,
        ssh_key_path=config.ssh_key_path,
        extra_excludes=config.rsync_excludes,
    )
    a_log = FileLogAdapter(config.local_log_path, config.log_retention_days)
    b_log = SshLogAdapter(
        host=config.remote_host,
        user=config.remote_user,
        key_path=config.ssh_key_path,
        remote_log_path=config.remote_log_path,
    )

    service = SyncService(git=git, transfer=transfer, a_log=a_log, b_log=b_log)

    try:
        service.sync(is_first_run=is_first_run)
    except Exception as exc:
        print(f"ERROR: sync failed: {exc}", file=sys.stderr)
        sys.exit(1)

    head = _get_head_hash(config.httdocs_path)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(head + "\n")
    sys.exit(0)


def _get_head_hash(repo_path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()
