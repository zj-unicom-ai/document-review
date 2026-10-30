# 开发者指南

本文面向希望参与开发、调试或打包项目的贡献者。

## 环境要求

- Python 3.12+
- Node.js 22+
- Docker Engine 24+
- Docker Compose v2
- MySQL 8（生产部署）

## 获取代码

```bash
git clone <repository-url>
cd document-review
```

## Python 环境

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
pip install --no-deps -e ./packages/core
pip install -e ".[dev,lint]"
```

`requirements.lock` 锁定运行时依赖和构建工具。开发工具仍由 editable 安装的
optional dependencies 提供。

## 本地配置

```bash
cp .env.example .env
```

默认 SQLite 适合本地开发。如连接 MySQL，请配置 `DB_*` 或 `DATABASE_URL`。
不要提交真实 `.env`。

## 数据库初始化

```bash
alembic upgrade head
python -m app.seed.load_seed
```

## 初始化平台超管

```bash
SUPERADMIN_INITIAL_PASSWORD=Changeme@2026 \
  python -m app.bootstrap.create_superadmin
```

## 启动后端

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 启动前端

```bash
cd web
npm ci
npm run dev
```

Vite 开发服务器会将 `/api` 代理到本地 FastAPI。

## 验证命令

### 后端

```bash
pytest
ruff check .
ruff format --check .
```

### 前端

在 `web/` 下执行：

```bash
npm run typecheck
npm run test -- --run
npm run build
```

### Compose 配置

```bash
docker compose --env-file .env.docker.example config --quiet
```

## 依赖锁

运行时依赖必须保持可复现：

```bash
python scripts/compile_python_lock.py --check
```

修改 `pyproject.toml` 依赖后执行：

```bash
python scripts/compile_python_lock.py
python scripts/compile_python_lock.py --check
```

如需解析 cutoff 之后的新版本，必须显式传入新的 cutoff，并同步复核
[NOTICE](../NOTICE.md) 与安全公告。

## 测试边界

- 测试中的 LLM 必须使用 fake provider 或 mock 服务；
- 测试不得访问真实外部 LLM 服务；
- 多租户行为必须有隔离断言；
- API 契约必须有 Pydantic 往返测试；
- 涉及外部系统的能力必须覆盖异常路径。

## 文档边界

公开文档不得引用：

- 真实客户或个人数据；
- 私有样例文件；
- 未公开内部系统；
- 真实密钥或内部地址；
- 未发布的业务规则结论。

修改公开文档时运行：

```bash
pytest tests/unit/test_public_docs.py -q
```

## 项目结构

```text
app/                  FastAPI 平台
packages/core/        可复用核心审核包
web/                  React 管理台
alembic/              数据库迁移
deploy/               Docker entrypoint 与 mock 服务
docs/                 公开文档
tests/                平台测试
```

## 提交前检查

提交前至少运行：

```bash
pytest
ruff check .
ruff format --check .

cd web
npm run typecheck
npm run test -- --run
npm run build
```

涉及部署或依赖的改动，还应运行：

```bash
python scripts/compile_python_lock.py --check
docker compose --env-file .env.docker.example config --quiet
```
