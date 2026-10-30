# 贡献指南

感谢你关注 Document Review。

## 开发原则

1. 平台能力保持通用，不内置特定行业、客户或地区规则；
2. 业务判断优先通过租户概念和规则表达；
3. 外部调用必须集中在适配层；
4. 新能力必须有正向与异常路径测试；
5. 公开文档不得引入私有数据或内部系统信息。

## 开发环境

参见 [Developer Guide](docs/developer-guide.md)。

## 提交前验证

后端：

```bash
pytest
ruff check .
ruff format --check .
```

前端：

```bash
cd web
npm run typecheck
npm run test -- --run
npm run build
```

依赖或部署变更：

```bash
python scripts/compile_python_lock.py --check
docker compose --env-file .env.docker.example config --quiet
```

公开文档变更：

```bash
pytest tests/unit/test_public_docs.py -q
```

PR 会自动执行 CI，覆盖后端测试与静态检查、Python 依赖锁复现、前端类型检查与
构建、依赖审计、Compose 配置校验以及发布资产扫描。

## 代码风格

- Python 标识符使用英文；
- 模块、类和公共函数使用中文 docstring；
- 注释保持简洁，优先解释“为什么”；
- 不主动重排无关代码；
- 不提交生成物、缓存、环境文件或私有样例。

## Pull Request 建议

PR 描述建议包含：

1. 变更目的；
2. 实现摘要；
3. 测试方式；
4. 风险与兼容性；
5. 文档更新情况。

小型修复保持聚焦；大型架构变更请先提交设计讨论。

## 安全问题

不要在 issue 或 PR 中暴露密钥、私有文档或漏洞细节。请按
[Security Policy](SECURITY.md) 报告。
