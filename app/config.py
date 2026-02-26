from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ai-recommendation-service"
    app_version: str = "0.1.0"
    app_port: int = 8001

    db_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DB_URL", "db_url"),
    )
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "postgres"
    db_user: str = Field(
        default="postgres",
        validation_alias=AliasChoices("DB_USER", "DB_USERNAME", "db_user"),
    )
    db_password: str = Field(
        default="postgres",
        validation_alias=AliasChoices("DB_PASSWORD", "db_password"),
    )

    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_API_KEY", "openai_api_key"),
    )
    ingest_excel_path: str = Field(
        default="",
        validation_alias=AliasChoices("INGEST_EXCEL_PATH", "ingest_excel_path"),
    )
    embedding_model: str = "text-embedding-3-small"
    chat_model: str = "gpt-4o-mini"
    llm_mode: str = "quick"
    llm_max_cases: int = 5
    llm_max_output_tokens: int = 380
    openai_timeout_seconds: float = 12.0

    # fast(5초 목표, 기본) | accuracy(정확도 우선)
    recommend_mode: str = Field(
        default="fast",
        validation_alias=AliasChoices("RECOMMEND_MODE", "recommend_mode"),
    )


settings = Settings()
