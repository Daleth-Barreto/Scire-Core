import pytest
from pydantic import SecretStr
from typer.testing import CliRunner

from backend.core.config import Settings
from backend.core.envfile import mask, set_env_value, unset_env_value
from cli.main import app

runner = CliRunner()


def test_secret_not_exposed_via_stringification(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-super-secret-123")
    settings = Settings(_env_file=None)
    assert "sk-super-secret-123" not in str(settings)
    assert "sk-super-secret-123" not in repr(settings)
    assert "sk-super-secret-123" not in str(settings.model_dump())


def test_provider_api_key_raises_when_missing(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    settings = Settings(_env_file=None)
    with pytest.raises(ValueError, match="is not set"):
        settings.provider_api_key  # noqa: B018


def test_envfile_set_unset(tmp_path):
    env = tmp_path / ".env"
    set_env_value(env, "OMNIROUTE_API_KEY", "sk-1234567890")
    set_env_value(env, "GITHUB_TOKEN", "ghp-token-value")
    assert "OMNIROUTE_API_KEY=sk-1234567890" in env.read_text()
    set_env_value(env, "OMNIROUTE_API_KEY", "sk-new-value")
    assert env.read_text().count("OMNIROUTE_API_KEY=") == 1
    assert "OMNIROUTE_API_KEY=sk-new-value" in env.read_text()

    unset_env_value(env, "GITHUB_TOKEN")
    assert "GITHUB_TOKEN" not in env.read_text()
    assert "OMNIROUTE_API_KEY=sk-new-value" in env.read_text()


def test_mask_hides_value():
    assert mask("sk-1234567890") == "sk-1****"
    assert mask("ab") == "****"
    assert mask("") == "(unset)"


def test_config_set_never_echoes_value(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    monkeypatch.setattr("cli.commands.config.ENV_PATH", env)
    monkeypatch.setattr("cli.commands.config.invalidate_settings", lambda: None)

    secret = "sk-SECRET-TOKEN-VALUE"
    result = runner.invoke(app, ["config", "set", "omniroute_api_key", secret])
    assert result.exit_code == 0
    assert secret not in result.output
    assert f"omniroute_api_key={secret}" in env.read_text()


def test_config_show_masks_secrets(tmp_path, monkeypatch):
    class FakeSettings:
        llm_provider = "omniroute"
        llm_model = "auto"
        openrouter_api_key = SecretStr("sk-OPENROUTER-VALUE")
        openai_api_key = SecretStr("")
        anthropic_api_key = SecretStr("")
        omniroute_api_key = SecretStr("sk-OMNIROUTE-SECRET")
        embed_provider = "omniroute"
        embed_model = "gemini/gemini-embedding-001"
        embed_api_key = SecretStr("")
        embed_dim = 3072
        database_url = "postgresql+psycopg://scire:scire@localhost:5432/scire"
        github_token = SecretStr("ghp-GITHUB-SECRET")

    monkeypatch.setattr("cli.commands.config.get_settings", lambda: FakeSettings())
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "sk-OMNIROUTE-SECRET" not in result.output
    assert "ghp-GITHUB-SECRET" not in result.output
    assert "sk-O****" in result.output
    assert "ghp-****" in result.output
    assert "gemini/gemini-embedding-001" in result.output


def test_config_rejects_unknown_key(tmp_path, monkeypatch):
    monkeypatch.setattr("cli.commands.config.ENV_PATH", tmp_path / ".env")
    result = runner.invoke(app, ["config", "set", "bogus_key", "x"])
    assert result.exit_code != 0
    assert "unknown config key" in result.output
