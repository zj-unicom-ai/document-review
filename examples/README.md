# Examples

本目录提供无业务含义的通用示例，不包含真实客户、行业结论或内部系统信息。

## 1. 生成通用 PDF

```bash
python examples/generate_demo_pdf.py --output examples/generated/project-summary.pdf
```

生成内容只包含一个通用的项目总结标题、资料提交状态和可追溯性说明，用于验证平台
解析与审查链路。

## 2. 启动 mock 服务

在 `.env.docker` 中配置：

```env
LLM_BASE_URL=http://mock-llm:8000/v1
LLM_API_KEY=mock-key
LLM_MODEL=mock

MINERU_PRIVATE_API_SERVER=http://mock-mineru:8000/file_parse
```

启动：

```bash
docker compose --env-file .env.docker --profile mocks up -d --build
```

## 3. 体验链路

1. 打开 Web；
2. 使用默认平台超管登录；
3. 创建“项目总结”概念与通用检查规则；
4. 上传生成的 `project-summary.pdf`；
5. 查看审查结果、trace 与批注 PDF。

详细页面操作见 [用户指南](../docs/user-guide.md)。
