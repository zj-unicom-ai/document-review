# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Centralized settings via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import quote_plus

from pydantic import AliasChoices, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["development", "test", "staging", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: AppEnv = "development"
    app_name: str = "document-review"
    app_version: str = "0.1.0"
    app_debug: bool = True
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_log_level: str = "INFO"

    # Database
    database_url: str | None = None
    db_host: str = Field("", validation_alias=AliasChoices("DB_HOST", "MYSQL_HOST"))
    db_port: int = Field(3306, validation_alias=AliasChoices("DB_PORT", "MYSQL_PORT"))
    db_user: str = Field("docrev", validation_alias=AliasChoices("DB_USER", "MYSQL_USER"))
    db_password: str = Field("", validation_alias=AliasChoices("DB_PASSWORD", "MYSQL_PASSWORD"))
    db_name: str = Field("document_review", validation_alias=AliasChoices("DB_NAME", "MYSQL_DB"))
    db_echo: bool = Field(False, validation_alias=AliasChoices("DB_ECHO", "MYSQL_ECHO"))
    db_pool_size: int = Field(10, validation_alias=AliasChoices("DB_POOL_SIZE", "MYSQL_POOL_SIZE"))
    db_max_overflow: int = Field(
        20, validation_alias=AliasChoices("DB_MAX_OVERFLOW", "MYSQL_MAX_OVERFLOW")
    )
    seed_standard_rules: bool = Field(False, validation_alias=AliasChoices("SEED_STANDARD_RULES"))

    # Redis：兼容旧 .env 中两级写法展开后的 URL / PORT / REDPASSWORD
    redis_host: str = Field(
        "127.0.0.1",
        validation_alias=AliasChoices("REDIS_HOST", "REDIC_CONFIG_HOST", "URL"),
    )
    redis_port: int = Field(
        6379,
        validation_alias=AliasChoices("REDIS_PORT", "REDIC_CONFIG_PORT", "PORT"),
    )
    redis_password: str = Field(
        "",
        validation_alias=AliasChoices("REDIS_PASSWORD", "REDIC_CONFIG_PASSWORD", "REDPASSWORD"),
    )
    redis_db: int = Field(
        0,
        validation_alias=AliasChoices("REDIS_DB", "REDIC_CONFIG_DB"),
    )
    llm_max_concurrency: int = 4

    # LLM
    llm_base_url: str = Field(
        "",
        validation_alias=AliasChoices("LLM_BASE_URL", "LLM_CONFIG_BASE_URL", "BASE_URL"),
    )
    llm_api_key: str = Field(
        "",
        validation_alias=AliasChoices("LLM_API_KEY", "LLM_CONFIG_API_KEY", "API_KEY"),
    )
    llm_model: str = Field(
        "",
        validation_alias=AliasChoices("LLM_MODEL", "LLM_CONFIG_MODEL", "MODEL"),
    )
    llm_text_base_url: str = Field(
        "",
        validation_alias=AliasChoices("LLM_TEXT_BASE_URL", "LLM_CONFIG_TEXT_BASE_URL"),
    )
    llm_text_api_key: str = Field(
        "",
        validation_alias=AliasChoices("LLM_TEXT_API_KEY", "LLM_CONFIG_TEXT_API_KEY"),
    )
    llm_text_model: str = Field(
        "",
        validation_alias=AliasChoices("LLM_TEXT_MODEL", "LLM_CONFIG_TEXT_MODEL"),
    )
    llm_request_timeout_s: int = Field(
        60,
        validation_alias=AliasChoices(
            "LLM_REQUEST_TIMEOUT_S",
            "LLM_CONFIG_REQUEST_TIMEOUT_S",
            "REQUEST_TIMEOUT_S",
        ),
    )
    llm_vision_base_url: str = Field(
        "",
        validation_alias=AliasChoices("LLM_VISION_BASE_URL", "LLM_CONFIG_VISION_BASE_URL"),
    )
    llm_vision_api_key: str = Field(
        "",
        validation_alias=AliasChoices("LLM_VISION_API_KEY", "LLM_CONFIG_VISION_API_KEY"),
    )
    llm_vision_model: str = Field(
        "",
        validation_alias=AliasChoices("LLM_VISION_MODEL", "LLM_CONFIG_VISION_MODEL"),
    )
    llm_light_base_url: str = Field(
        "",
        validation_alias=AliasChoices("LLM_LIGHT_BASE_URL", "LLM_CONFIG_LIGHT_BASE_URL"),
    )
    llm_light_api_key: str = Field(
        "",
        validation_alias=AliasChoices("LLM_LIGHT_API_KEY", "LLM_CONFIG_LIGHT_API_KEY"),
    )
    llm_light_model: str = Field(
        "",
        validation_alias=AliasChoices("LLM_LIGHT_MODEL", "LLM_CONFIG_LIGHT_MODEL"),
    )
    llm_profile_discovery: bool = Field(
        True,
        validation_alias=AliasChoices("LLM_PROFILE_DISCOVERY", "LLM_CONFIG_PROFILE_DISCOVERY"),
    )
    cross_check_enabled: bool = Field(False, validation_alias=AliasChoices("CROSS_CHECK_ENABLED"))

    # Auth
    auth_secret_key: str = ""
    auth_session_ttl_seconds: int = 12 * 60 * 60

    # Storage
    storage_root: str = "./storage"
    agent_api_key: str = ""
    agent_timeout_s: int = Field(default=600, ge=1, le=3600)
    agent_max_pages: int = Field(default=100, ge=1, le=1000)
    agent_max_upload_mb: int = Field(default=50, ge=1, le=200)

    # Optional integrations
    mineru_provider: str = Field(
        "",
        validation_alias=AliasChoices("MINERU_PROVIDER", "MINERU_CONFIG_PROVIDER"),
    )
    mineru_api_base: str = Field(
        "",
        validation_alias=AliasChoices("MINERU_API_BASE", "MINERU_CONFIG_API_BASE"),
    )
    mineru_token: str = Field(
        "",
        validation_alias=AliasChoices("MINERU_TOKEN", "MINERU_CONFIG_TOKEN"),
    )
    mineru_model_version: str = Field(
        "vlm",
        validation_alias=AliasChoices("MINERU_MODEL_VERSION", "MINERU_CONFIG_MODEL_VERSION"),
    )
    mineru_language: str = Field(
        "ch",
        validation_alias=AliasChoices("MINERU_LANGUAGE", "MINERU_CONFIG_LANGUAGE"),
    )
    mineru_poll_interval_seconds: int = Field(
        5,
        validation_alias=AliasChoices(
            "MINERU_POLL_INTERVAL_SECONDS",
            "MINERU_CONFIG_POLL_INTERVAL_SECONDS",
        ),
    )
    mineru_max_polls: int = Field(
        10,
        validation_alias=AliasChoices("MINERU_MAX_POLLS", "MINERU_CONFIG_MAX_POLLS"),
    )
    mineru_timeout_seconds: int = Field(
        60,
        validation_alias=AliasChoices("MINERU_TIMEOUT_SECONDS", "MINERU_CONFIG_TIMEOUT_SECONDS"),
    )
    mineru_enable_table: bool = Field(
        True,
        validation_alias=AliasChoices("MINERU_ENABLE_TABLE", "MINERU_CONFIG_ENABLE_TABLE"),
    )
    mineru_enable_formula: bool = Field(
        True,
        validation_alias=AliasChoices("MINERU_ENABLE_FORMULA", "MINERU_CONFIG_ENABLE_FORMULA"),
    )
    mineru_private_api_server: str = Field(
        "",
        validation_alias=AliasChoices(
            "MINERU_PRIVATE_API_SERVER", "MINERU_CONFIG_PRIVATE_API_SERVER"
        ),
    )
    mineru_private_backend: str = Field(
        "",
        validation_alias=AliasChoices("MINERU_PRIVATE_BACKEND", "MINERU_CONFIG_PRIVATE_BACKEND"),
    )
    elasticsearch_url: str = ""
    langfuse_base_url: str = ""

    # MinIO：保留原两级配置中的值，但 .env 必须使用扁平键
    minio_upload_url: str = Field(
        "", validation_alias=AliasChoices("MINIO_UPLOAD_URL", "UPLOAD_URL")
    )
    minio_access_key: str = Field(
        "", validation_alias=AliasChoices("MINIO_ACCESS_KEY", "ACCESS_KEY")
    )
    minio_secret_key: str = Field(
        "", validation_alias=AliasChoices("MINIO_SECRET_KEY", "SECRET_KEY")
    )
    minio_public_policy_bucket: str = Field(
        "",
        validation_alias=AliasChoices("MINIO_PUBLIC_POLICY_BUCKET", "PUBLIC_POLICY_BUCKET"),
    )
    minio_endpoint: str = Field("", validation_alias=AliasChoices("MINIO_ENDPOINT", "ENDPOINT"))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redis_url(self) -> str:
        """拼装 Redis 连接地址；密码与库号按需包含。"""
        password = quote_plus(self.redis_password)
        return f"redis://:{password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def async_database_url(self) -> str:
        """Return the SQLAlchemy async URL to use at runtime."""
        if self.database_url:
            return self.database_url
        pwd = quote_plus(self.db_password)
        return (
            f"mysql+aiomysql://{self.db_user}:{pwd}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sync_database_url(self) -> str:
        """Sync URL for Alembic (Alembic uses sync drivers only)."""
        if self.database_url and self.database_url.startswith("sqlite"):
            return self.database_url.replace("+aiosqlite", "")
        pwd = quote_plus(self.db_password)
        return (
            f"mysql+pymysql://{self.db_user}:{pwd}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_sqlite(self) -> bool:
        return (self.database_url or "").startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
