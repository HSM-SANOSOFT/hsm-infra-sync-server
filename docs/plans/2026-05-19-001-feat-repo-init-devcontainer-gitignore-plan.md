---
title: "feat: Repo initialization — devcontainer and .gitignore"
type: feat
status: completed
date: 2026-05-19
origin: docs/brainstorms/repo-init-requirements.md
---

# feat: Repo initialization — devcontainer and .gitignore

## Summary

Create the two scaffolding files needed before sync logic work begins: a VS Code devcontainer giving a lean Ubuntu shell with `git`, `rsync`, and `ssh`; and a `.gitignore` keeping generated, secret, and OS-noise files out of version control.

---

## Problem Frame

Repo is a blank slate. Without a devcontainer, each contributor sets up tooling manually. Without a `.gitignore`, noise files (OS artifacts, secrets, runtime state) risk getting committed.

---

## Requirements

- R1. `devcontainer.json` — VS Code compatible, `remoteUser: vscode`, lean Linux base, `git`/`rsync`/`ssh` available inside container
- R2. `.gitignore` — covers env files, logs, Windows/macOS OS artifacts, IDE files, sync runtime artifacts

---

## Scope Boundaries

- No PHP/Apache tooling in the container
- No port forwarding
- No CI/CD configuration
- No actual sync scripts or logic

---

## Context & Research

### Relevant Code and Patterns

- Origin: `docs/brainstorms/repo-init-requirements.md`
- Claude Code devcontainer reference: https://code.claude.com/docs/en/devcontainer
- Microsoft devcontainer base images: `mcr.microsoft.com/devcontainers/base:ubuntu`
- Devcontainer features registry: `ghcr.io/devcontainers/features/` (provides clean tool installation without shell scripting)

### Institutional Learnings

- None applicable — greenfield repo

---

## Key Technical Decisions

- **Base image: `mcr.microsoft.com/devcontainers/base:ubuntu`** — Microsoft's official lean devcontainer base; no language runtime bundled, smallest surface area for a tooling-only container
- **rsync + ssh via devcontainer features** — cleaner than a `postCreateCommand` shell script; features handle idempotent installation declaratively
- **Ubuntu not Windows** — Docker runs Linux containers by default (WSL2/Docker Desktop); `rsync` has no native Windows container support; target being Windows servers does not require the dev environment to be Windows

---

## Output Structure

    .devcontainer/
      devcontainer.json
    .gitignore

---

## Implementation Units

- U1. **devcontainer.json**

**Goal:** VS Code devcontainer giving a lean Ubuntu shell with `git`, `rsync`, and `ssh` client available; `remoteUser` set to `vscode`

**Requirements:** R1

**Dependencies:** None

**Files:**
- Create: `.devcontainer/devcontainer.json`

**Approach:**
- Use `mcr.microsoft.com/devcontainers/base:ubuntu` as base image
- Add `rsync` and `ssh` via devcontainer features (`ghcr.io/devcontainers/features/` registry)
- Set `remoteUser: vscode`
- No `forwardPorts` — not needed
- No `postCreateCommand` — features handle installation

**Patterns to follow:**
- Official VS Code devcontainer spec: https://code.claude.com/docs/en/devcontainer

**Test scenarios:**
- Happy path: `git clone` repo → open in VS Code → "Reopen in Container" → container builds without error
- Happy path: inside container shell, `git --version`, `rsync --version`, `ssh -V` all succeed
- Happy path: `whoami` inside container returns `vscode`

**Verification:**
- Container opens in VS Code without build errors
- All three tools (`git`, `rsync`, `ssh`) respond to `--version` / `-V` inside the container shell
- `whoami` returns `vscode`

---

- U2. **.gitignore**

**Goal:** Prevent generated, secret, and OS-noise files from being tracked by git

**Requirements:** R2

**Dependencies:** None

**Files:**
- Create: `.gitignore`

**Approach:**
- Cover env files (`.env`, `.env.*`; keep `.env.example` with negation)
- Cover log files (`*.log`, `logs/`)
- Cover Windows OS artifacts (`Thumbs.db`, `desktop.ini`, `$RECYCLE.BIN/`)
- Cover macOS artifacts (`.DS_Store`)
- Cover IDE files (`.vscode/` with negations for `extensions.json` and `settings.json` so team config is tracked, `.idea/`)
- Cover sync tool runtime artifacts (`.bak`, `.sync`, `.sync-state/`)

**Test scenarios:**
- Happy path: `git status` on a fresh clone shows no untracked noise files for any covered category
- Edge case: `.env.example` is NOT ignored (negation rule works)
- Edge case: `.vscode/extensions.json` and `.vscode/settings.json` are NOT ignored

**Verification:**
- `git check-ignore -v <file>` confirms each covered artifact type is ignored
- `.env.example`, `.vscode/extensions.json`, `.vscode/settings.json` are not ignored

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| devcontainer feature for rsync not available in registry | Fall back to `postCreateCommand: "sudo apt-get install -y rsync"` |
| VS Code devcontainer extension not installed locally | Not a plan concern — developer prerequisite |

---

## Sources & References

- **Origin document:** [docs/brainstorms/repo-init-requirements.md](docs/brainstorms/repo-init-requirements.md)
- Claude Code devcontainer docs: https://code.claude.com/docs/en/devcontainer
