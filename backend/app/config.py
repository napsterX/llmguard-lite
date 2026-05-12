from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "LLMGuard Lite"
    debug: bool = False
    database_url: str = "postgresql://llmguard:llmguard@localhost:5432/llmguard"
    anthropic_api_key: str = ""
    openai_api_key: str = ""


settings = Settings()
