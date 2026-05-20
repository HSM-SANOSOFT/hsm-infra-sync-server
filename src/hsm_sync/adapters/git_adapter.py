from __future__ import annotations

import subprocess
from pathlib import Path

from hsm_sync.core.models import FileChange


class GitAdapter:
    def __init__(self, repo_path: Path) -> None:
        self._repo = repo_path

    def commit(self, message: str) -> None:
        subprocess.run(
            ["git", "-C", str(self._repo), "add", "-A"],
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self._repo), "commit", "-m", message, "--allow-empty"],
            capture_output=True,
            text=True,
            check=True,
        )

    def get_changed_files(self) -> list[FileChange]:
        count_proc = subprocess.run(
            ["git", "-C", str(self._repo), "rev-list", "--count", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        if count_proc.stdout.strip() == "1":
            # Initial commit — no parent to diff against
            return []

        diff_proc = subprocess.run(
            ["git", "-C", str(self._repo), "diff", "HEAD~1", "HEAD", "--name-status"],
            capture_output=True,
            text=True,
            check=True,
        )
        return _parse_name_status(diff_proc.stdout)


def _parse_name_status(output: str) -> list[FileChange]:
    changes = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status_field = parts[0]
        if status_field.startswith("R"):
            # R100\told.php\tnew.php
            new_path = parts[2] if len(parts) >= 3 else parts[1]
            changes.append(FileChange(path=new_path, status="R"))
        else:
            changes.append(FileChange(path=parts[1], status=status_field))
    return changes
