# 配置说明

配置来自环境变量或 `.env` 文件。Docker Compose 推荐先执行：

```bash
python scripts/setup_docker.py
```

该脚本会生成本机 `.env.docker`，并随机生成数据库口令与 `AUTH_SECRET_KEY`。
不要提交任何真实环境文件。

## 应用

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_ENV` | `development` | `development` / `test` / `staging` / `production` |
| `APP_NAME` | `document-review` | 服务名 |
| `APP_VERSION` | `0.1.0` | 应用版本 |
| `APP_DEBUG` | `true` | 生产必须为 `false` |
| `APP_LOG_LEVEL` | `INFO` | 日志级别 |
| `RUN_PLATFORM_SEED` | Docker 下 `true` | 是否同步通用平台元数据 |

## 认证

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `AUTH_SECRET_KEY` | 空 | 生产必填；推荐 `openssl rand -base64 48` |
| `AUTH_SESSION_TTL_SECONDS` | `43200` | 登录会话有效期 |
| `SUPERADMIN_INITIAL_PASSWORD` | Docker 镜像内为 `Changeme@2026` | 仅用于激活空密码超管 |
| `BOOTSTRAP_SUPERADMIN` | `true` | Docker 启动时执行幂等超管初始化 |

生产环境缺少 `AUTH_SECRET_KEY` 会启动失败。修改过超管密码后，重启不会重置密码。

## 数据库

### 使用拆分变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DB_HOST` | 空 | MySQL 主机 |
| `DB_PORT` | `3306` | MySQL 端口 |
| `DB_USER` | 空 | 应用账号 |
| `DB_PASSWORD` | 空 | 应用密码 |
| `DB_NAME` | `document_review` | 数据库名 |
| `DB_POOL_SIZE` | `10` | 连接池大小 |
| `DB_MAX_OVERFLOW` | `20` | 最大溢出连接 |
| `DB_ECHO` | `false` | SQL echo |

### 使用完整 URL

可设置 `DATABASE_URL`，例如：

```env
DATABASE_URL=mysql+aiomysql://user:password@host:3306/document_review?charset=utf8mb4
```

本地开发也可使用 SQLite：

```env
DATABASE_URL=sqlite+aiosqlite:///./local.db
```

生产建议使用 MySQL，并确保数据库备份已启用。

## Redis

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `REDIS_HOST` | `127.0.0.1` | Redis 主机 |
| `REDIS_PORT` | `6379` | Redis 端口 |
| `REDIS_PASSWORD` | 空 | Redis 密码 |
| `REDIS_DB` | `0` | Redis 数据库编号 |

## LLM

平台通过 OpenAI-compatible API 接入模型。共享配置适合简单部署；生产建议按
`text` / `vision` / `light` 档位拆分。

### 共享配置

| 变量 | 说明 |
| --- | --- |
| `LLM_BASE_URL` | API base URL，例如 `https://example.com/v1` |
| `LLM_API_KEY` | API key |
| `LLM_MODEL` | 主模型名 |
| `LLM_REQUEST_TIMEOUT_S` | 请求超时，默认 60 秒 |
| `LLM_MAX_CONCURRENCY` | 并发上限，默认 4 |

### 档位配置

每个档位支持以下变量：

```text
LLM_TEXT_BASE_URL
LLM_TEXT_API_KEY
LLM_TEXT_MODEL

LLM_VISION_BASE_URL
LLM_VISION_API_KEY
LLM_VISION_MODEL

LLM_LIGHT_BASE_URL
LLM_LIGHT_API_KEY
LLM_LIGHT_MODEL
```

未配置档位专用 base URL 或 model 时回退共享配置。

### 其他开关

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LLM_PROFILE_DISCOVERY` | `true` | 未知结构文档是否启用 LLM 画像发现 |
| `CROSS_CHECK_ENABLED` | `false` | 可选交叉检查 |

## MinerU

支持 self-host `/file_parse` 兼容接口或 cloud ZIP 模式。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `MINERU_PROVIDER` | 空 | `self_host` 或 `cloud_zip` |
| `MINERU_PRIVATE_API_SERVER` | 空 | self-host `/file_parse` 地址 |
| `MINERU_API_BASE` | 空 | cloud API base |
| `MINERU_TOKEN` | 空 | cloud token |
| `MINERU_PRIVATE_BACKEND` | 空 | self-host backend |
| `MINERU_MODEL_VERSION` | `vlm` | 模型版本 |
| `MINERU_LANGUAGE` | `ch` | 语言 |
| `MINERU_TIMEOUT_SECONDS` | `60` | 请求超时 |
| `MINERU_POLL_INTERVAL_SECONDS` | `5` | cloud 轮询间隔 |
| `MINERU_MAX_POLLS` | `10` | cloud 最大轮询次数 |
| `MINERU_ENABLE_TABLE` | `true` | 启用表格 |
| `MINERU_ENABLE_FORMULA` | `true` | 启用公式 |

未配置 MinerU 时平台可启动，PDF 解析相关请求会返回明确错误。

## 存储

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `STORAGE_ROOT` | `./storage` | 上传、artifact 与批注 PDF 根目录 |

Docker 默认使用 `document-review_storage-data` named volume。删除卷会删除上传
文件、解析产物和批注 PDF，操作前必须备份。

## 调用方无状态审核 API

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `AGENT_API_KEY` | 空 | 保护 `/api/v1/evaluations/` |
| `AGENT_TIMEOUT_S` | `600` | 执行超时 |
| `AGENT_MAX_PAGES` | `100` | 最大页数 |
| `AGENT_MAX_UPLOAD_MB` | `50` | 最大上传大小 |

## 可选集成

| 变量 | 说明 |
| --- | --- |
| `ELASTICSEARCH_URL` | Elasticsearch 地址 |
| `LANGFUSE_BASE_URL` | 自托管 Langfuse 地址 |
| `MINIO_UPLOAD_URL` | MinIO 上传地址 |
| `MINIO_ACCESS_KEY` | MinIO access key |
| `MINIO_SECRET_KEY` | MinIO secret key |
| `MINIO_PUBLIC_POLICY_BUCKET` | 公共策略 bucket |
| `MINIO_ENDPOINT` | MinIO endpoint |

可选集成为空时平台可启动，相关扩展能力不生效。

## Docker Compose 变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `COMPOSE_PROJECT_NAME` | `document-review` | Compose project |
| `API_PORT` | `8000` | API 宿主机端口 |
| `WEB_PORT` | `8080` | Web 宿主机端口 |
| `MYSQL_BIND_HOST` | `127.0.0.1` | MySQL 宿主机发布地址；默认仅本机可访问 |
| `MYSQL_PORT` | `3306` | MySQL 宿主机端口；默认只绑定到 `MYSQL_BIND_HOST` |
| `MYSQL_ROOT_PASSWORD` | 无 | MySQL root 密码 |
| `MYSQL_DATABASE` | `document_review` | 初始数据库 |
| `MYSQL_USER` | `document_review` | MySQL 应用账号 |
| `MYSQL_PASSWORD` | 无 | MySQL 应用密码 |

## 相关文档

- [部署指南](deployment.md)
- [运维手册](operations.md)
- [安全说明](security.md)
