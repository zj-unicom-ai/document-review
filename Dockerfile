# syntax=docker/dockerfile:1
# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10 \
    STORAGE_ROOT=/app/storage

WORKDIR /app

# 第三方依赖全部来自带 hash 的锁文件，避免构建时动态解析版本。
COPY requirements.lock ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --require-hashes -r requirements.lock

# 本地包依赖已由锁文件安装，这里只安装源码本身。
COPY pyproject.toml README.md ./
COPY packages/core/pyproject.toml packages/core/README.md packages/core/
COPY packages/core/src packages/core/src

RUN pip install --no-deps --no-build-isolation -e ./packages/core

# 再安装平台及其剩余依赖。
COPY app app
COPY alembic alembic
COPY alembic.ini ./
COPY deploy/backend-entrypoint.sh deploy/backend-entrypoint.sh
RUN pip install --no-deps --no-build-isolation -e . \
    && chmod +x deploy/backend-entrypoint.sh \
    && useradd --uid 10001 --create-home appuser

# 通用源码镜像不携带业务规则种子和样例；.dockerignore 已排除。
RUN mkdir -p /app/storage \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=2)"]

ENTRYPOINT ["./deploy/backend-entrypoint.sh"]
