# hsm-infra-sync-server

Automated one-way file sync from a Windows source server (A) to a Windows replica server (B). On each scheduled run it commits any file changes to a local git repo, then mirrors the folder to Server B over SFTP — including deletions. Runs as a Windows Task Scheduler job every 15 minutes.

**No Python or any other tooling required on the server.** `hsm-sync.exe` is a single self-contained executable built by CI and downloaded from GitHub Releases.

---

## How it works

1. `hsm-sync.exe` reads `.env` from its working directory
2. Stages and commits all changes in the watched folder to git
3. Connects to Server B over SSH and syncs the folder via SFTP — uploading new/changed files and deleting files removed on A
4. Writes a JSON log entry on Server A and appends a receipt to Server B's log
5. Prunes log entries older than 7 days on Server A

---

## Requirements

| Machine | Requirements |
|---|---|
| Server A (source) | Git installed; `hsm-sync.exe` + `.env` in the same folder |
| Server B (replica) | OpenSSH Server enabled (Windows optional feature) |
| Build machine | `uv` — only for building the exe, not needed on servers |

---

## Deploy

### 1. Download the executable

Go to [Releases](../../releases) and download `hsm-sync.exe` from the latest release. Place it in a dedicated folder on Server A, e.g. `C:/hsm-sync/`.

### 2. Configure

Copy `.env.example` to `.env` in the same folder as the exe and fill in all values:

```
C:/hsm-sync/
  hsm-sync.exe
  .env          ← copy from .env.example and edit
```

See [Configuration reference](#configuration-reference) below for every variable.

### 3. Set up SSH key authentication

On Server A, generate a dedicated key pair:

```powershell
ssh-keygen -t ed25519 -f C:/Users/deploy/.ssh/hsm_sync -N ""
```

This produces two files:
- `hsm_sync` — **private key** → set `SSH_PRIVATE_KEY_PATH` to this path in `.env`
- `hsm_sync.pub` — **public key** → append its contents to Server B's `C:/Users/deploy/.ssh/authorized_keys`

Verify the connection works before registering the scheduled task:

```powershell
ssh -i C:/Users/deploy/.ssh/hsm_sync deploy@192.168.1.100 echo ok
```

If Server B is not yet in Server A's `known_hosts`, add it:

```powershell
ssh-keyscan 192.168.1.100 >> C:/Users/deploy/.ssh/known_hosts
```

### 4. Test a manual run

```powershell
cd C:/hsm-sync
./hsm-sync.exe
```

Check that `logs/sync.log` was created on Server A and that files appeared on Server B.

### 5. Register the scheduled task

Edit `taskscheduler/hsm-sync.xml` — update `<Command>`, `<WorkingDirectory>`, and `<UserId>` to match your paths and Windows account — then import it:

```powershell
schtasks /Create /XML taskscheduler\hsm-sync.xml /TN "HSM Sync" /RU "DOMAIN\deploy" /RP
```

Or import via the Task Scheduler GUI: **Action → Import Task…**

Confirm the task is registered:

```powershell
schtasks /Query /TN "HSM Sync" /FO LIST
```

---

## Configuration reference

All values live in `.env` next to the exe. Use forward slashes for all paths (`C:/path/to/dir`).

### Required

| Variable | Description |
|---|---|
| `HOST_FOLDER_TO_SYNC_PATH` | Folder on Server A to sync (must already be a git repo) |
| `REMOTE_HOST` | Server B IP address or hostname |
| `REMOTE_USER` | SSH username on Server B |
| `REMOTE_FOLDER_TO_SYNC_PATH` | Destination folder on Server B (SFTP path) |
| `SSH_PRIVATE_KEY_PATH` | Path to the **private** key file on Server A |
| `REMOTE_LOG_PATH` | Path to the append log file on Server B |

### Optional

| Variable | Default | Description |
|---|---|---|
| `HOST_LOG_PATH` | `logs/sync.log` | JSON-lines log on Server A |
| `LOG_RETENTION_DAYS` | `7` | Days to keep A-side log entries before pruning |
| `STATE_FILE_PATH` | `.hsm-sync-state` beside `HOST_LOG_PATH` | Tracks last synced commit hash; absence = full sync |
| `RSYNC_EXCLUDES` | _(empty)_ | Extra comma-separated patterns to exclude from sync |

**Built-in excludes** (always applied): `.git`, `.env`, `.env.*`, `logs/`, `__pycache__/`, `*.pyc`

---

## Logs

**Server A** — `HOST_LOG_PATH`: one JSON line per run, pruned automatically after `LOG_RETENTION_DAYS`.

```json
{"timestamp": "2026-05-20T12:00:00+00:00", "changed_files": [{"path": "index.php", "status": "M"}], "rsync_exit_code": 0, "bytes_transferred": 1234, "is_first_run": false}
```

**Server B** — `REMOTE_LOG_PATH`: same JSON format, appended via SSH on each run. Not pruned.

---

## Building the executable

CI builds and publishes `hsm-sync.exe` automatically on every push to `main`. To build locally on a Windows machine:

```powershell
# Requires uv: https://docs.astral.sh/uv
.\scripts\build-exe.ps1
# Output: dist\hsm-sync.exe  (~40-60 MB, fully self-contained)
```

---

## CI / releases

Every push to `main` runs the release workflow (`.github/workflows/release.yml`):

1. Bumps the patch version in `pyproject.toml`
2. Runs the full test suite on `windows-latest` — aborts if any test fails
3. Builds `hsm-sync.exe` with PyInstaller
4. Creates a GitHub Release tagged `v{version}` with the exe attached

---

## Development

```powershell
uv sync          # install dependencies (requires uv)
uv run pytest    # run tests
uv run ruff check src/  # lint
```

The codebase follows a hexagonal architecture — core domain logic in `src/hsm_sync/core/` has no subprocess or SSH imports. Adapters in `src/hsm_sync/adapters/` implement the ports and are injected at runtime, so the full test suite runs with no real SSH or git required.
