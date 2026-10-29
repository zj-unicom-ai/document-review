# Third-Party Notices

本项目自身代码采用 [MIT License](LICENSE) 授权：

```text
Copyright (c) 2026 Document Review Contributors
```

本文件仅帮助使用者识别第三方依赖的授权类型，不修改任何第三方软件自身的
license、商标或免责声明。集成、分发或商业化使用前，应以各依赖包携带的完整
license 文本与法务意见为准。

Python 与 npm 的完整锁定组件清单见 [sbom/dependencies.csv](sbom/dependencies.csv)。

## 重要授权提示：PyMuPDF

本项目声明依赖 `PyMuPDF`。PyMuPDF / MuPDF 采用：

```text
GNU AFFERO GENERAL PUBLIC LICENSE 3.0 (AGPL-3.0)
或 Artifex Commercial License
```

这意味着：

- 若使用 AGPL-3.0 路径，分发包含 PyMuPDF 的软件或提供网络服务时，需自行评估
  并履行 AGPL-3.0 的源码提供、开源义务与其他要求；
- 若不希望接受 AGPL-3.0 义务，应自行向 Artifex 获取适用范围的商业授权；
- 本项目首版仅发布源码，不发布官方 Docker 镜像或二进制发行包；
- 用户执行 `docker build`、安装依赖或分发镜像时，会自行引入 PyMuPDF，需自行
  确认所选授权路径；
- 本项目源码采用 MIT，不改变 PyMuPDF 及其他第三方依赖的授权义务。

## Python 直接依赖

| 依赖 | License | 说明 |
| --- | --- | --- |
| `document-review-core` | MIT | 本项目内置核心包 |
| `fastapi` | MIT | Web API |
| `uvicorn[standard]` | BSD-3-Clause | ASGI server，standard extra 另含各自许可的依赖 |
| `python-multipart` | Apache-2.0 | multipart 解析 |
| `pydantic` | MIT | 数据校验 |
| `pydantic-settings` | MIT | 配置管理 |
| `sqlalchemy[asyncio]` | MIT | ORM / database engine |
| `alembic` | MIT | migration |
| `aiomysql` | MIT | MySQL async driver |
| `PyMySQL[rsa]` | MIT | MySQL protocol / RSA full auth 支持 |
| `aiosqlite` | MIT | SQLite async driver |
| `redis` | MIT | Redis client |
| `langgraph` | MIT | 图编排 |
| `langchain-core` | MIT | LLM 抽象 |
| `langchain-openai` | MIT | OpenAI-compatible provider |
| `jsonschema` | MIT | JSON Schema 校验 |
| `PyMuPDF` | AGPL-3.0 或 Artifex Commercial License | 见上文重要授权提示 |
| `Pillow` | Pillow / MIT-CMU-HP 等项目自有 permissive license | 图像处理 |
| `structlog` | Apache-2.0 OR MIT | 结构化日志 |
| `tenacity` | Apache-2.0 | 重试 |
| `httpx` | BSD-3-Clause | HTTP client |

### 重要传递依赖

| 依赖 | 引入路径 | License |
| --- | --- | --- |
| `cryptography` | `PyMySQL[rsa]` | Apache-2.0 OR BSD-3-Clause |
| `starlette` | `fastapi` | BSD-3-Clause |
| `openai` | `langchain-openai` | Apache-2.0 |
| `annotated-types` / `pydantic-core` | `pydantic` | MIT |

Python 运行时依赖由 `requirements.lock` 锁定。升级或新增依赖时必须重新生成
锁文件，并同步复核本文件、锁文件中的实际版本与包内 license 文本；后续引入
SBOM 后，应将本表与锁定版本一并生成或校验。

## 前端直接依赖

| 依赖 | 类型 | License |
| --- | --- | --- |
| `@tanstack/react-query` | runtime | MIT |
| `react` | runtime | MIT |
| `react-dom` | runtime | MIT |
| `react-pdf` | runtime | MIT |
| `react-router-dom` | runtime | MIT |
| `@testing-library/jest-dom` | dev | MIT |
| `@testing-library/react` | dev | MIT |
| `@testing-library/user-event` | dev | MIT |
| `@types/react` | dev | MIT |
| `@types/react-dom` | dev | MIT |
| `@vitejs/plugin-react` | dev | MIT |
| `jsdom` | dev | MIT |
| `openapi-typescript` | dev | Apache-2.0 |
| `typescript` | dev | Apache-2.0 |
| `vite` | dev | MIT |
| `vitest` | dev | MIT |

### 重要前端传递依赖

| 依赖 | 引入路径 | License |
| --- | --- | --- |
| `pdfjs-dist` | `react-pdf` | Apache-2.0 |
| `rollup` | `vite` | MIT |
| `esbuild` | `vite` | MIT |

前端锁定版本见 `web/package-lock.json`。升级依赖或变更 lockfile 时，应同步更新
本文件。
