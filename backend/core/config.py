from functools import lru_cache
import threading

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# In-memory session keys, decrypted from the encrypted key store after unlock.
# Never persisted; cleared on lock or process exit.
_session_keys: dict[str, str] = {}
_session_lock = threading.Lock()


def get_session_keys() -> dict[str, str]:
    with _session_lock:
        return dict(_session_keys)


def set_session_keys(keys: dict[str, str]) -> None:
    with _session_lock:
        _session_keys.clear()
        _session_keys.update({key: value for key, value in keys.items() if value})


def clear_session_keys() -> None:
    with _session_lock:
        _session_keys.clear()


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

    def _session_value(self, env_name: str) -> str | None:
        return get_session_keys().get(env_name) or None

    @property
    def provider_api_key(self) -> SecretStr:
        session_val = self._session_value(f"{self.llm_provider}_api_key".upper())
        if session_val:
            return SecretStr(session_val)
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
        session_val = self._session_value(f"{self.embed_provider}_api_key".upper())
        if session_val:
            return SecretStr(session_val)
        keys = {
            "openai": self.openai_api_key,
            "omniroute": self.omniroute_api_key,
        }
        key = keys[self.embed_provider]
        if not key.get_secret_value():
            raise ValueError(f"API key for embed provider '{self.embed_provider}' is not set")
        return key

    def effective_github_token(self) -> SecretStr:
        session_val = self._session_value("GITHUB_TOKEN")
        if session_val:
            return SecretStr(session_val)
        return self.github_token


@lru_cache
def get_settings() -> Settings:
    return Settings()


def invalidate_settings() -> None:
    get_settings.cache_clear()
