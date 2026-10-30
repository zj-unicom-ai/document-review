# 运维手册

## 升级

```bash
# 1. 备份数据库和 storage 卷；
# 2. 拉取或构建新版本；
docker compose --env-file .env.docker pull
docker compose --env-file .env.docker up -d --build
# 3. 观察 readiness 和错误日志。
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker logs -f api
```

API 容器每次启动执行 `alembic upgrade head`；Alembic 版本表保证重复执行幂等。
升级前必须确认数据库备份可恢复。

## 备份

```bash
mkdir -p backup/$(date +%F)
docker compose --env-file .env.docker exec mysql \
  sh -c 'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction "$MYSQL_DATABASE"' \
  > "backup/$(date +%F)/database.sql"
docker run --rm \
  -v "$(pwd)/backup/$(date +%F)":/backup \
  -v "${COMPOSE_PROJECT_NAME:-document-review}_storage-data:/data:ro" \
  alpine tar -czf /backup/storage.tgz -C /data .
```

`mysqldump` 输出包含敏感业务数据，必须存放到受限目录。

## 恢复

```bash
docker compose --env-file .env.docker exec -T mysql \
  sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"' \
  < backup/<date>/database.sql

docker run --rm \
  -v "$(pwd)/backup/<date>":/backup:ro \
  -v "${COMPOSE_PROJECT_NAME:-document-review}_storage-data:/data" \
  alpine sh -c 'rm -rf /data/* && tar -xzf /backup/storage.tgz -C /data'
```

恢复后重启 API 并检查 `/health/ready`。

## 故障排查

| 现象 | 检查 |
| --- | --- |
| API unready | `docker compose logs mysql api`；确认数据库健康和 DB 口令。MySQL 短暂重启后 readiness 应自动恢复；持续 503 时查看 API 是否出现数据库认证或连接错误。 |
| 前端可打开但接口失败 | 浏览器请求路径是否 `/api/v1`；查看 `web` 与 `api` 日志。 |
| 解析失败提示 URL 未配置 | 设置 `MINERU_PRIVATE_API_SERVER` 或启用 mock。 |
| LLM 调用失败 | 检查 `LLM_BASE_URL / LLM_API_KEY / LLM_MODEL`。 |
| 磁盘增长 | 检查 `storage-data` 中 uploads / artifacts / annotated PDF，并按保留策略归档。 |

## 回滚

1. 停止当前 API / web；
2. 恢复上一个镜像 tag；
3. 如数据库 migration 已执行，不手工改历史 migration；使用项目提供的 forward
   migration 或最近数据库备份恢复；
4. 恢复 storage 卷；
5. 启动后验证 readiness、登录/租户配置、上传、审查和批注下载。
