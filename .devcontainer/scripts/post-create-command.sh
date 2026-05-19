#!/bin/bash
set -e

# Post-create user-level setup (no sudo — runs as vscode).
# System packages (rsync, etc.) are installed in the Dockerfile.
