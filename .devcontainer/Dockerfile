FROM mcr.microsoft.com/devcontainers/python:3.13

USER root

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y rsync \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

USER vscode

RUN uv tool install ruff@latest \
    && uv tool install ty@latest

ENV PATH="/home/vscode/.local/bin:$PATH"

RUN mkdir -p /home/vscode/.claude && chown -R vscode:vscode /home/vscode/.claude