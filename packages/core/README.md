# document-review-core

同一套无状态审核引擎供独立 FastAPI 服务及其他 Python 后端复用。
包名 document_review，不包含 app、数据库模型、租户管理或业务报告类型。
公共入口 EvaluationRequest、EvaluationResponse、EvaluationService。
模型配置显式注入；核心包不读取 .env。部署与验证见仓库 docs/embedding.md。
