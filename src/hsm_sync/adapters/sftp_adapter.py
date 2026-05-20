from __future__ import annotations

import fnmatch
import os
import stat as stat_mod
from pathlib import Path

import paramiko

from hsm_sync.core.models import SyncResult

# Paths/names to never transfer (checked against each path component)
_DEFAULT_EXCLUDES = [
    ".git",
    ".git/",
    ".env",
    ".env.*",
    "logs",
    "logs/",
    "__pycache__",
    "__pycache__/",
    "*.pyc",
]


class SftpAdapter:
    def __init__(
        self,
        source_path: Path,
        remote_host: str,
        remote_user: str,
        remote_path: str,
        ssh_key_path: Path,
        extra_excludes: list[str] | None = None,
    ) -> None:
        self._source = source_path
        self._host = remote_host
        self._user = remote_user
        self._remote = remote_path.rstrip("/").rstrip("\\")
        self._key = ssh_key_path
        self._excludes = _DEFAULT_EXCLUDES + (extra_excludes or [])

    def sync(self, is_first_run: bool) -> SyncResult:
        client = _ssh_connect(self._host, self._user, self._key)
        try:
            sftp = client.open_sftp()
            bytes_transferred = self._sync_tree(sftp)
        finally:
            client.close()
        return SyncResult(
            changed_files=[],
            rsync_exit_code=0,
            bytes_transferred=bytes_transferred,
            is_first_run=is_first_run,
        )

    def _sync_tree(self, sftp: paramiko.SFTPClient) -> int:
        local_files = self._walk_local()
        remote_files = _walk_remote(sftp, self._remote)
        bytes_transferred = 0

        # Upload new files and files whose size changed
        for rel, local_size in local_files.items():
            remote_p = f"{self._remote}/{rel}"
            if rel not in remote_files or remote_files[rel] != local_size:
                _sftp_makedirs(sftp, remote_p.rsplit("/", 1)[0])
                local_abs = self._source / Path(rel.replace("/", os.sep))
                sftp.put(str(local_abs), remote_p)
                bytes_transferred += local_size

        # Delete files on B that no longer exist on A
        for rel in set(remote_files) - set(local_files):
            try:
                sftp.remove(f"{self._remote}/{rel}")
            except OSError:
                pass

        return bytes_transferred

    def _walk_local(self) -> dict[str, int]:
        """Return {posix_rel_path: size} for all non-excluded files under source."""
        result: dict[str, int] = {}
        for dirpath, dirnames, filenames in os.walk(self._source):
            dirnames[:] = [
                d for d in dirnames if not _is_excluded(d + "/", self._excludes)
            ]
            for fname in filenames:
                full = Path(dirpath) / fname
                rel = full.relative_to(self._source).as_posix()
                if not _is_excluded(rel, self._excludes):
                    result[rel] = full.stat().st_size
        return result


def _ssh_connect(host: str, user: str, key_path: Path) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.connect(
        host,
        username=user,
        key_filename=str(key_path),
        look_for_keys=False,
        allow_agent=False,
    )
    return client


def _walk_remote(sftp: paramiko.SFTPClient, path: str) -> dict[str, int]:
    """Return {posix_rel_path: size} for all regular files under remote path."""
    result: dict[str, int] = {}
    try:
        _collect_remote(sftp, path, path, result)
    except OSError:
        pass  # Remote path doesn't exist yet (first run or empty target)
    return result


def _collect_remote(
    sftp: paramiko.SFTPClient, base: str, current: str, out: dict[str, int]
) -> None:
    for attr in sftp.listdir_attr(current):
        full = f"{current}/{attr.filename}"
        rel = full[len(base) :].lstrip("/")
        mode = attr.st_mode or 0
        if stat_mod.S_ISDIR(mode):
            _collect_remote(sftp, base, full, out)
        elif stat_mod.S_ISREG(mode):
            out[rel] = attr.st_size or 0


def _sftp_makedirs(sftp: paramiko.SFTPClient, path: str) -> None:
    """Recursively create remote directory, silently ignoring existing dirs."""
    if not path or path == "/" or path.rstrip("/").endswith(":"):
        return
    try:
        sftp.stat(path)
        return  # Already exists
    except OSError:
        pass
    parent = path.rsplit("/", 1)[0]
    if parent and parent != path:
        _sftp_makedirs(sftp, parent)
    try:
        sftp.mkdir(path)
    except OSError:
        pass  # Race condition or root-level path


def _is_excluded(rel: str, patterns: list[str]) -> bool:
    """True if any path component of rel matches any exclude pattern."""
    rel = rel.replace("\\", "/")
    parts = rel.split("/")
    for pattern in patterns:
        if fnmatch.fnmatch(rel, pattern):
            return True
        for part in parts:
            if fnmatch.fnmatch(part, pattern.rstrip("/")) or fnmatch.fnmatch(
                part + "/", pattern
            ):
                return True
    return False
