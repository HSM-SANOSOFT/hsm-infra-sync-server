---
date: 2026-05-19
topic: server-sync-tool
---

# Server Sync Tool

## Summary

A Python cron tool that runs on Server A, commits httdocs state to git, uses git diff to produce a changelog, then rsyncs the full httdocs tree (including deletions) to Server B over SSH. All config via `.env`; 7-day rolling logs on both servers.

---

## Problem Frame

Two legacy web servers (A and B) must stay in sync. Server A holds the canonical codebase (httdocs). Server B is the replica. No CI/CD pipeline exists and adding one would disrupt the production workflow. Changes happen in-place on A. Currently there is no automated mechanism to propagate those changes to B — manual transfers are error-prone and easy to miss. The tool must run as a cron job with zero operator involvement per sync cycle.

---

## Actors

- A1. **Server A (primary)**: Hosts the canonical httdocs. Runs the cron job and the sync script.
- A2. **Server B (replica)**: Receives synced files. No git required. Target path mirrors A's httdocs root.
- A3. **Sync script**: Python process that orchestrates commit → log → transfer.
- A4. **Operator**: Deploys the tool, configures `.env`, monitors logs.

---

## Key Flows

- F1. **Scheduled sync**
  - **Trigger:** Cron job fires on Server A at configured interval
  - **Actors:** A1, A2, A3
  - **Steps:**
    1. Script reads config from `.env` (paths, SSH key, B's host/user/path, log config)
    2. `git add -A` and `git commit` in httdocs on A — commits all pending changes with a timestamp message
    3. `git diff HEAD~1 HEAD --name-status` produces the changelog for logging
    4. rsync over SSH (`--checksum --delete`) from A's httdocs to B's httdocs
    5. Write A-side log entry: timestamp, changed files, rsync exit status, bytes transferred
    6. Write B-side log entry via SSH: timestamp, confirmation of receipt
    7. Prune A-side log entries older than 7 days
  - **Outcome:** B's httdocs matches A's httdocs; both logs updated.
  - **Covered by:** R1, R2, R3, R4, R5, R6, R7, R9, R10

- F2. **First run / cold start**
  - **Trigger:** Script runs with no prior sync baseline
  - **Actors:** A1, A2, A3
  - **Steps:**
    1. Detect no prior sync state (first-run marker absent or forced via flag)
    2. Commit current httdocs state to git on A
    3. rsync `--checksum --delete` — transfers only files that differ from what B already has
    4. Log full-sync run on A and B
  - **Outcome:** B contains all files from A's httdocs; files already correct on B are not re-transferred.
  - **Covered by:** R3, R8

---

## Requirements

**Git integration**
- R1. On each run, the script stages all changes in httdocs (`git add -A`) and creates a git commit with a timestamp-based message.
- R2. After committing, the script extracts the list of changed, added, renamed, and deleted files from `git diff HEAD~1 HEAD --name-status`.

**File transfer**
- R3. The script transfers httdocs from A to B using rsync over SSH with checksum comparison (`--checksum`) and deletion propagation (`--delete`).
- R4. The rsync target host, user, and path on B are configurable via `.env`.
- R5. Files deleted on A are deleted on B within the same sync run.
- R8. On first run, the tool performs a full rsync — only transferring files that differ from what B already has (rsync default behavior).

**Logging**
- R6. A-side log records per-run: timestamp, list of files changed (from git diff), rsync exit status, and bytes transferred.
- R7. B-side log is written per run via SSH: timestamp and confirmation of receipt.
- R9. A-side log retains entries for 7 rolling days; entries older than 7 days are pruned on each run.
- R10. Log file path on A is configurable via `.env`.

**Configuration**
- R11. All environment-specific values are read from a `.env` file: httdocs path on A, target host/user/path on B, SSH key path, log path, and any optional flags.
- R12. The script contains no hardcoded paths, credentials, or hostnames.

**Testing**
- R13. Unit tests cover git operations (commit, diff parsing), log writing and rotation, and rsync command construction.
- R14. SSH and rsync calls are mockable — no real SSH connection required to run the test suite.

---

## Acceptance Examples

- AE1. **Covers R1, R2.** Given two files were edited in httdocs since the last run, when the script runs, it commits both and the git diff output lists exactly those two files as modified.
- AE2. **Covers R5.** Given a file exists on both A and B, when that file is deleted on A and the script runs, rsync removes it from B in the same sync cycle.
- AE3. **Covers R8.** Given B already has most files from a previous manual copy, when the script runs for the first time, only files that differ by checksum are transferred — files already correct on B are not re-sent.
- AE4. **Covers R9.** Given log entries exist from 8 days ago, when the script runs, those entries are pruned and only the last 7 days remain.
- AE5. **Covers R13, R14.** Given a mocked SSH client and a temporary git repo, when the test suite runs, all tests pass without a real SSH connection or live server.

---

## Success Criteria

- B's httdocs is identical to A's httdocs within one cron interval of any change on A.
- Deletions on A propagate to B reliably in the same sync run.
- A-side logs provide a clear per-run record of what changed; 7-day retention holds.
- Test suite passes with no external dependencies (no real SSH, no live servers).
- All config values live in `.env`; deploying to a new environment requires editing only `.env`.

---

## Scope Boundaries

- No CI/CD pipeline integration.
- No bidirectional sync (B→A is out of scope).
- No multi-replica support (single B target only) in v1.
- No web dashboard or alerting; logs are plain files.
- No automatic cron installation — operator configures crontab manually.
- `.env` and `.git/` are excluded from sync.
- B does not need git installed.

---

## Key Decisions

- **rsync over SCP per-file**: rsync handles deletions, partial transfers, checksumming, and retries natively. SCP would require custom logic for all edge cases.
- **git diff for log, rsync for transfer**: git provides the meaningful human-readable changelog; rsync provides reliable idempotent transfer. They are complementary, not redundant.
- **Python over Bash**: Bash is natural for cron scripts but testing is painful and error handling is fragile at scale. Python enables proper unit tests and clean `.env` loading.
- **Checksum-based rsync (`--checksum`)**: Avoids relying on timestamps, which can drift between servers. Slower per run but more accurate.

---

## Dependencies / Assumptions

- `rsync` and `ssh` are installed on Server A.
- SSH key authentication is configured between A and B (no password prompts in cron context).
- A→B outbound SSH is not blocked on Server A (not yet tested — must be verified before deployment).
- httdocs on A is a valid git repo with at least one prior commit.
- Operator has SSH access to A to deploy the script and configure crontab (currently blocked from laptop — stated as fixable).
- Python 3 is available on Server A.

---

## Outstanding Questions

### Resolve Before Planning

- None.

### Deferred to Planning

- [Affects R9][Technical] Log rotation: prune old lines in a single rolling log file vs. write dated log files and delete old files.
- [Affects R6, R7][Technical] B-side log format: append to a single file on B vs. per-run timestamped files.
- [Affects R3][Needs research] rsync exclude flags: confirm the right set to exclude `.env`, `.git/`, and any A-specific files from transfer.
