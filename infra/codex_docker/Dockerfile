# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.14
ARG NODE_VERSION=24
ARG CODEX_VERSION=latest

FROM node:${NODE_VERSION}-bookworm-slim AS node

FROM python:${PYTHON_VERSION}-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/home/codex \
    CODEX_HOME=/home/codex/.codex \
    XDG_CACHE_HOME=/tmp/.cache \
    MPLCONFIGDIR=/tmp/matplotlib \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    NPM_CONFIG_FUND=false \
    NPM_CONFIG_AUDIT=false

# ツールをインストール
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      bash \
      bubblewrap \
      jq \
      ripgrep \
      fd-find \
      file \
      findutils \
      coreutils \
      procps \
    && rm -rf /var/lib/apt/lists/*

# Node.js 本体と npm 一式をコピー
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules

# npm / npx / corepack の symlink を作り直す
RUN ln -sf ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -sf ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && ln -sf ../lib/node_modules/corepack/dist/corepack.js /usr/local/bin/corepack \
    && node --version \
    && npm --version \
    && npx --version

# Codex CLI
RUN --mount=type=cache,target=/root/.npm \
    npm i -g @openai/codex@${CODEX_VERSION} \
    && npm cache clean --force \
    && codex --version

# データ分析用 Python ライブラリ
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install \
      numpy \
      pandas \
      scipy \
      scikit-learn \
      statsmodels \
      matplotlib \
      pyarrow \
      openpyxl \
      xlrd \
      duckdb \
      polars \
      pyyaml \
      beautifulsoup4 \
      lxml

RUN mkdir -p \
      /home/codex/.codex \
      /workspace \
      /workspace/data_source \
      /workspace/artifacts \
      /workspace/tmp \
      /tmp/.cache \
      /tmp/matplotlib \
    && chmod 0777 \
      /home/codex \
      /home/codex/.codex \
      /workspace \
      /workspace/data_source \
      /workspace/artifacts \
      /workspace/tmp \
      /tmp/.cache \
      /tmp/matplotlib \
    && groupadd -g 1000 codex \
    && useradd -u 1000 -g 1000 -M -d /home/codex -s /bin/bash codex

WORKDIR /workspace

USER 1000:1000

CMD ["bash"]