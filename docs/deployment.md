# 通用平台 Docker 部署指南

本文面向通用文档规则审查平台的开源使用者。默认部署是空业务库：平台只初始化通用
元数据，不包含行业规则包、历史报告、地市样例或真实凭据。

## 前置要求

- Docker Engine 24+ 与 Docker Compose v2；
- 可写本地目录用于保存 `.env.docker`；
- 如需真实解析 / 模型能力，准备好 LLM 与 MinerU endpoint 和密钥。

## 默认启动

Docker 构建使用 `requirements.lock` 安装带 hash 校验的 Python 第三方依赖，
并以固定解析截止时间复现版本；本地源码包不会参与动态依赖解析。

```bash
python scripts/setup_docker.py

docker compose --env-file .env.docker up -d --build
```

`setup_docker.py` 会生成本机 `.env.docker`：

- 随机生成 `MYSQL_ROOT_PASSWORD` / `MYSQL_PASSWORD` / `AUTH_SECRET_KEY`；
- 固定写入平台超管初始密码 `SUPERADMIN_INITIAL_PASSWORD=Changeme@2026`；
- 文件权限为 `0600`；
- 已存在 `.env.docker` 时拒绝覆盖，避免丢失本机密钥。

启动后访问：

- Web：`http://localhost:${WEB_PORT}`，默认 `http://localhost:8080`；
- API health：`http://localhost:${API_PORT}/health`；
- API readiness：`http://localhost:${API_PORT}/health/ready`；
- OpenAPI：`http://localhost:${API_PORT}/docs`。

`RUN_PLATFORM_SEED=true` 只同步通用平台机制元数据（算子登记）。业务规则
包由使用者在界面/API 中按租户配置。

## 初始平台超管

- 保留租户：`superadmin`
- 平台超管账号：`admin`
- 初始密码：`Changeme@2026`

后端容器会在 migration 与通用 seed 后执行幂等初始化。只有 migration 生成的空密码
账号会被激活；如果账号已有密码（包括使用者后续修改过的密码），重启时会跳过初始
化，不会覆盖。首次登录后请立即修改该密码。

## 使用内置 mock

mock 用于验证平台机制，不表达任何业务判断：

```bash
cp .env.docker.example .env.docker
```

在 `.env.docker` 中设置：

```env
MINERU_PRIVATE_API_SERVER=http://mock-mineru:8000/file_parse
LLM_BASE_URL=http://mock-llm:8000/v1
LLM_API_KEY=mock-key
LLM_MODEL=mock
```

启动 mock profile：

```bash
docker compose --env-file .env.docker --profile mocks up -d --build
```

## 配置能力

| 配置为空时的行为 |
| --- |
| LLM endpoint 为空：LLM 相关调用提示服务未配置，平台仍可启动。 |
| MinerU endpoint 为空：PDF 解析相关请求失败并提示未配置，平台仍可启动。 |
| MinIO 为空：使用容器内 `/app/storage` volume。 |
| Elasticsearch / Langfuse 未启用：相关可选扩展不生效。 |

## 日常操作

查看状态：

```bash
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker logs -f api web
```

停止并保留数据：

```bash
docker compose --env-file .env.docker down
```

停止并删除容器、网络，数据卷仍保留：

```bash
docker compose --env-file .env.docker down --remove-orphans
```

删除数据卷属于破坏性操作，执行前必须先完成备份并二次确认。

## 健康语义

- `/health`：进程可响应；
- `/health/ready`：API 可连接数据库；
- Compose 中 API 使用 `/health/ready`，数据库不可用时会显示 unready；
- MySQL、Redis、web、mock 服务均有独立 healthcheck。
