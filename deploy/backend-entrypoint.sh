#!/bin/sh
# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

set -eu

# 通用镜像默认连接 MySQL；显式 SQLite 场景允许本地开发复用镜像。
case "${DATABASE_URL:-}" in
  sqlite*)
    :
    ;;
  *)
    for key in DB_HOST DB_PORT DB_USER DB_PASSWORD DB_NAME; do
      eval "value=\${$key:-}"
      if [ -z "$value" ]; then
        echo "部署配置缺失: $key 必须设置" >&2
        exit 78
      fi
    done
    ;;
esac

if [ "${SEED_STANDARD_RULES:-false}" = "true" ]; then
  echo "当前发行包不包含可选规则包数据: 请保持 SEED_STANDARD_RULES=false" >&2
  exit 78
fi

if [ "${APP_ENV:-production}" = "production" ] && [ -z "${AUTH_SECRET_KEY:-}" ]; then
  echo "部署配置缺失: AUTH_SECRET_KEY 必须设置" >&2
  exit 78
fi

echo "正在执行数据库迁移..."
alembic upgrade head

if [ "${RUN_PLATFORM_SEED:-true}" = "true" ]; then
  echo "正在初始化通用平台元数据..."
  python -m app.seed.load_seed
fi

# 固定初始密码只用于激活 migration 生成的空密码账号；已有密码时命令内部会跳过。
if [ "${BOOTSTRAP_SUPERADMIN:-true}" = "true" ]; then
  export SUPERADMIN_INITIAL_PASSWORD="${SUPERADMIN_INITIAL_PASSWORD:-Changeme@2026}"
  echo "正在初始化平台超管..."
  python -m app.bootstrap.initialize_superadmin
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
