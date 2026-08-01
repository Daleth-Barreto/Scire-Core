from pathlib import Path

import typer

from backend.core.config import get_settings, invalidate_settings
from backend.core.envfile import mask, set_env_value, unset_env_value

config_app = typer.Typer(help="Manage local configuration (.env).")

ENV_PATH = Path(".env")

CONFIG_FIELDS: list[tuple[str, bool]] = [
    ("llm_provider", False),
    ("llm_model", False),
    ("openrouter_api_key", True),
    ("openai_api_key", True),
    ("anthropic_api_key", True),
    ("omniroute_api_key", True),
    ("embed_provider", False),
    ("embed_model", False),
    ("embed_api_key", True),
    ("embed_dim", False),
    ("database_url", False),
    ("github_token", True),
]

KNOWN_KEYS = {name for name, _ in CONFIG_FIELDS}


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Config key"),
    value: str = typer.Argument(..., help="Value (never echoed back)"),
) -> None:
    if key not in KNOWN_KEYS:
        raise typer.BadParameter(
            f"unknown config key '{key}'; keys: {', '.join(sorted(KNOWN_KEYS))}"
        )
    set_env_value(ENV_PATH, key, value)
    invalidate_settings()
    typer.echo(f"set {key}")


@config_app.command("unset")
def config_unset(key: str = typer.Argument(...)) -> None:
    if key not in KNOWN_KEYS:
        raise typer.BadParameter(
            f"unknown config key '{key}'; keys: {', '.join(sorted(KNOWN_KEYS))}"
        )
    unset_env_value(ENV_PATH, key)
    invalidate_settings()
    typer.echo(f"unset {key}")


@config_app.command("show")
def config_show() -> None:
    settings = get_settings()
    for name, secret in CONFIG_FIELDS:
        if secret:
            value = mask(getattr(settings, name).get_secret_value())
        else:
            value = str(getattr(settings, name))
        typer.echo(f"{name}: {value}")
