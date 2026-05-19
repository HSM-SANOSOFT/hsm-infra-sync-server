# Repo Initialization — Requirements

**Date:** 2026-05-19
**Status:** Ready for planning

---

## Goal

Initialize `hsm-infra-sync-server` repo with a working local dev environment and clean version control hygiene before any sync logic is built.

The sync tool itself will use **git** for change tracking and **rsync** for file transfer between servers (Server A → Server B). This repo is the tooling layer — not the PHP/Apache codebase being synced.

---

## Requirements

### 1. Dev Container (VS Code)

- Use the official VS Code dev container spec (`devcontainer.json`)
- Reference: [Claude Code devcontainer docs](https://code.claude.com/docs/en/devcontainer)
- `remoteUser` must be `vscode`
- Base image: lean Linux (Ubuntu/Debian) — no PHP/Apache needed, this is the sync tool environment
- Include: `git`, `rsync`, `ssh` client
- No ports need forwarding

### 2. `.gitignore`

Cover:

- Environment files (`.env`, `.env.*`, keep `.env.example`)
- Logs (`*.log`, `logs/`)
- Windows OS artifacts (`Thumbs.db`, `desktop.ini`, `$RECYCLE.BIN/`)
- IDE files (`.vscode/` user-local settings, `.idea/`)
- macOS artifacts (`.DS_Store`)
- Sync tool runtime artifacts (`.bak`, `.sync`, `.sync-state/`)

---

## Out of Scope

- Actual sync logic (git tracking + rsync implementation)
- PHP/Apache configuration — not part of this repo
- Windows server connection setup (SSH keys, credentials)
- CI/CD pipelines

---

## Success Criteria

- `git clone` + "Reopen in Container" in VS Code gives a dev shell with `git`, `rsync`, and `ssh` available
- No generated, secret, or OS-noise files tracked by git
