from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://aquinas:aquinas@localhost:5432/aquinas"

    app_env: str = Field(default="development", validation_alias="APP_ENV")

    embedding_provider: str = Field(default="deterministic", validation_alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="hash-1536", validation_alias="EMBEDDING_MODEL")
    embedding_dimension: int = Field(default=1536, validation_alias="EMBEDDING_DIMENSION")
    embedding_api_key: SecretStr | None = Field(default=None, validation_alias="EMBEDDING_API_KEY")
    embedding_version: str = Field(
        default="test-v1",
        validation_alias="EMBEDDING_VERSION",
        description="CLI default target for M9; informational until versioning lands.",
    )
    embedding_batch_size: int = Field(default=100, validation_alias="EMBEDDING_BATCH_SIZE")
    embedding_timeout_s: float = Field(default=60.0, validation_alias="EMBEDDING_TIMEOUT_S")
    allow_deterministic_embeddings: bool = Field(
        default=False,
        validation_alias="ALLOW_DETERMINISTIC_EMBEDDINGS",
    )


settings = Settings()