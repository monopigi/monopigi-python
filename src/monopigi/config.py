"""Token and config storage in ~/.monopigi/config.toml."""

import tomllib
from pathlib import Path
from typing import NamedTuple

DEFAULT_CONFIG_PATH = Path.home() / ".monopigi" / "config.toml"
DEFAULT_BASE_URL = "https://api.monopigi.com"


class Config(NamedTuple):
    """Typed config structure."""

    token: str
    base_url: str


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> Config:
    """Load config from TOML file. Returns defaults if file doesn't exist."""
    if not config_path.exists():
        return Config(token="", base_url=DEFAULT_BASE_URL)
    with open(config_path, "rb") as f:
        data = tomllib.load(f)
    return Config(
        token=data.get("token", ""),
        base_url=data.get("base_url", DEFAULT_BASE_URL),
    )


def _escape_toml_string(value: str) -> str:
    """Escape a string for safe TOML embedding."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def save_config(
    token: str,
    base_url: str = DEFAULT_BASE_URL,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> None:
    """Save config to TOML file."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    safe_token = _escape_toml_string(token)
    safe_url = _escape_toml_string(base_url)
    content = f'token = "{safe_token}"\nbase_url = "{safe_url}"\n'
    config_path.write_text(content)
