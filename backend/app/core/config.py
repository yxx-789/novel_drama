from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_novel_studio"
    REDIS_URL: str = "redis://localhost:6379/0"
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    CHROMA_PERSIST_DIR: str = "./chroma_data"
    FERNET_SECRET: str = ""

    # LLM default config (fallback when no api_configs record)
    LLM_INTERFACE_FORMAT: str = "openai"
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-chat"
    LLM_API_KEY: str = ""
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 8192
    LLM_TIMEOUT: int = 600


settings = Settings()
