from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "scire"

    llm_provider: str = "openrouter"
    llm_model: str = ""
    openrouter_api_key: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")
    anthropic_api_key: SecretStr = SecretStr("")
    omniroute_api_key: SecretStr = SecretStr("")

    embed_provider: str = "openai"
    embed_model: str = ""
    embed_api_key: SecretStr = SecretStr("")
    embed_dim: int = 3072

    database_url: str = "postgresql+psycopg://scire:scire@localhost:5432/scire"

    github_token: SecretStr = SecretStr("")

    @property
    def provider_api_key(self) -> SecretStr:
        keys = {
            "openrouter": self.openrouter_api_key,
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "omniroute": self.omniroute_api_key,
        }
        key = keys[self.llm_provider]
        if not key.get_secret_value():
            raise ValueError(f"API key for provider '{self.llm_provider}' is not set")
        return key

    @property
    def embed_api_key_for_provider(self) -> SecretStr:
        keys = {
            "openai": self.openai_api_key,
            "omniroute": self.omniroute_api_key,
        }
        key = keys[self.embed_provider]
        if not key.get_secret_value():
            raise ValueError(f"API key for embed provider '{self.embed_provider}' is not set")
        return key


@lru_cache
def get_settings() -> Settings:
    return Settings()


def invalidate_settings() -> None:
    get_settings.cache_clear()
