# Document Review

Document Review 是一个可私有化部署的多租户文档智能审查平台。租户可以在管理台中
定义语义概念、规则和规则集，上传 PDF 后由平台完成解析、证据定位、规则执行、
违规汇总与批注 PDF 生成。

平台定位是通用文档规则审查引擎：平台内置的是解析、画像、规则执行、审计与权限
能力，不内置特定行业、客户或地区的业务规则。业务概念与规则由租户按自己的文档
口径配置。

## 核心能力

- 多租户与菜单级 RBAC；
- 概念、分类、规则与规则集管理；
- 通用检查能力目录与参数表单；
- PDF 解析、结构画像与证据定位；
- 确定性规则编排与 LLM 结构化审查；
- 审查进度、违规结果与规则 trace；
- 批注 PDF 生成与下载；
- Docker Compose 一键部署、备份恢复与运维手册；
- 可选 mock LLM / mock MinerU，便于无外部服务体验完整链路。

## 当前边界

v0.1.0 是首个开源源码版本：

- 首版仅发布源码，不发布官方 Docker 镜像或二进制发行包；使用者通过
  Docker Compose 在本地构建镜像。
- 平台不内置行业、客户或地区业务规则；概念和规则由租户显式配置。
- 外部资源适配器仍在建设中，外部数据核验未配置适配器时按规则错误策略处理。
- 平台未内置登录限速、账号锁定或验证码；公网或不可信网络部署必须由反向代理
  提供 HTTPS、限速和 body size 限制。
- OpenAPI `/docs` 与 `/redoc` 默认开启；公开环境应按需限制访问。
- 管理台界面当前仅提供简体中文。

## Roadmap

- 完善外部资源适配器与更多通用检查能力；
- 增加平台内置的登录限速、账号锁定与生产安全开关；
- 提升大规模文档与高并发审查性能；
- 丰富使用文档、演示素材和部署样例；
- 持续改进可观测性、备份恢复和升级工具。

## 快速开始

### 1. 生成部署配置

```bash
python scripts/setup_docker.py
```

脚本会生成 `.env.docker`，并为以下值生成随机密钥：

- MySQL root 密码；
- MySQL 应用密码；
- `AUTH_SECRET_KEY`。

### 2. 启动平台

```bash
docker compose --env-file .env.docker up -d --build
```

启动完成后访问：

- Web：`http://localhost:8080`
- API readiness：`http://localhost:8000/health/ready`
- OpenAPI：`http://localhost:8000/docs`

### 3. 登录平台超管

首次启动会自动初始化：

```text
租户：superadmin
账号：admin
初始密码：Changeme@2026
```

该初始密码只用于激活空密码账号。登录后请立即修改密码；容器重启不会覆盖已经
修改过的密码。

### 4. 使用 mock 体验完整审查

如暂无真实 LLM 或 MinerU 服务，可使用内置 mock：

```bash
python scripts/setup_docker.py
# 在 .env.docker 中设置 mock endpoint 后执行：
docker compose --env-file .env.docker --profile mocks up -d --build
```

推荐 mock 配置：

```env
LLM_BASE_URL=http://mock-llm:8000/v1
LLM_API_KEY=mock-key
LLM_MODEL=mock

MINERU_PRIVATE_API_SERVER=http://mock-mineru:8000/file_parse
```

mock 只用于验证平台链路，不表达任何业务判断。

## 常见问题

### 忘记平台超管密码怎么办？

首次启动默认密码为 `Changeme@2026`。登录后请立即修改；如果后续忘记密码，需要管理员
通过受控数据库运维流程重置账号密码，或从初始化前的备份恢复。

### 没有 LLM 或 MinerU 服务可以体验吗？

可以。使用 `--profile mocks` 启动内置 mock LLM 与 mock MinerU，即可体验上传、解析、
规则执行、trace 与批注 PDF 生成。mock 不表达任何业务判断。

### MySQL 会被暴露到局域网吗？

默认不会。Compose 仅把 MySQL 发布到宿主机 `127.0.0.1`。确需远程访问时，再显式修改
`MYSQL_BIND_HOST` 和防火墙策略。

### 生产环境如何暴露 Web 和 API？

建议只把 Web / API 暴露给反向代理，由反向代理提供 HTTPS、访问日志、限速和 body size
限制。平台当前未内置登录限速或账号锁定。

### PyMuPDF 的授权有什么注意事项？

项目自身采用 MIT，但 PyMuPDF / MuPDF 采用 AGPL-3.0 或 Artifex Commercial License。
分发软件、镜像或提供相关网络服务前，必须自行确认并履行所选授权路径义务。

### 如何备份和恢复数据？

参见 [运维与备份](docs/operations.md)。至少需要同时备份 MySQL volume 与 storage
volume，并定期验证备份可恢复。

### 有可运行的示例吗？

有。参见 [Examples](examples/README.md)，可生成一份无业务含义的通用 PDF，并使用
mock 服务体验完整审查链路。

## 文档

| 主题 | 文档 |
| --- | --- |
| 架构概览 | [Architecture](docs/architecture.md) |
| 部署 | [Deployment](docs/deployment.md) |
| 配置 | [Configuration](docs/configuration.md) |
| 使用指南 | [User Guide](docs/user-guide.md) |
| 开发指南 | [Developer Guide](docs/developer-guide.md) |
| 安全说明 | [Security](docs/security.md) |
| 运维与备份 | [Operations](docs/operations.md) |
| 变更记录 | [Changelog](CHANGELOG.md) |
| 示例 | [Examples](examples/README.md) |
| 依赖清单 | [SBOM](sbom/dependencies.csv) |
| 贡献指南 | [Contributing](CONTRIBUTING.md) |
| 漏洞报告 | [Security Policy](SECURITY.md) |

## 本地开发

后端：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
pip install --no-deps -e ./packages/core
pip install -e ".[dev,lint]"

cp .env.example .env
alembic upgrade head
python -m app.seed.load_seed

SUPERADMIN_INITIAL_PASSWORD=Changeme@2026 \
  python -m app.bootstrap.create_superadmin

uvicorn app.main:app --reload
```

前端：

```bash
cd web
npm ci
npm run dev
```

## 技术栈

- Python 3.12 / FastAPI
- SQLAlchemy 2 / Alembic / MySQL
- React / Vite / TanStack Query
- LangGraph / langchain-core
- MinerU-compatible PDF 解析接口
- OpenAI-compatible LLM API

## 授权

本项目自身代码采用 [MIT License](LICENSE)

第三方依赖遵循其各自 license。特别注意：`PyMuPDF` / MuPDF 采用
`AGPL-3.0` 或 `Artifex Commercial License` 双授权。分发包含 PyMuPDF 的软件、
镜像或提供相关网络服务前，必须自行确认并履行所选授权路径的义务。详见
[NOTICE](NOTICE.md)。

特别鸣谢 [UniRouter 联通词元平台 →](https://www.uni-router.net/)
