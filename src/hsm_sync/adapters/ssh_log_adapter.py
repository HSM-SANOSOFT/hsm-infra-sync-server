from __future__ import annotations

import json
import sys
from pathlib import Path

import paramiko

from hsm_sync.adapters.file_log_adapter import _entry_to_dict
from hsm_sync.core.models import LogEntry


class SshLogAdapter:
    def __init__(
        self,
        host: str,
        user: str,
        key_path: Path,
        remote_log_path: str,
    ) -> None:
        self._host = host
        self._user = user
        self._key = key_path
        self._remote_log_path = remote_log_path

    def write_entry(self, entry: LogEntry) -> None:
        json_line = json.dumps(_entry_to_dict(entry))
        try:
            client = paramiko.SSHClient()
            client.load_system_host_keys()
            client.set_missing_host_key_policy(paramiko.RejectPolicy())
            client.connect(
                self._host,
                username=self._user,
                key_filename=str(self._key),
                look_for_keys=False,
                allow_agent=False,
            )
            # type CON reads stdin and >> appends to the file under cmd.exe
            stdin, stdout, _stderr = client.exec_command(
                f'type CON >> "{self._remote_log_path}"'
            )
            stdin.write(json_line + "\n")
            stdin.channel.shutdown_write()
            exit_code = stdout.channel.recv_exit_status()
            client.close()
            if exit_code != 0:
                print(
                    f"WARNING: B-side log write failed (exit {exit_code})",
                    file=sys.stderr,
                )
        except Exception as exc:
            print(f"WARNING: B-side log write failed: {exc}", file=sys.stderr)

    def prune_old_entries(self) -> None:
        pass  # B-side log is not pruned by this tool
