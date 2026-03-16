"""Token and config storage in ~/.monopigi/config.toml."""

import tomllib
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".monopigi" / "config.toml"
DEFAULT_BASE_URL = "https://api.monopigi.com"


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> dict[str, str]:
    """Load config from TOML file. Returns defaults if file doesn't exist."""
    if not config_path.exists():
        return {"token": "", "base_url": DEFAULT_BASE_URL}
    with open(config_path, "rb") as f:
        data = tomllib.load(f)
    return {
        "token": data.get("token", ""),
        "base_url": data.get("base_url", DEFAULT_BASE_URL),
    }


def save_config(
    token: str,
    base_url: str = DEFAULT_BASE_URL,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> None:
    """Save config to TOML file."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    content = f'token = "{token}"\nbase_url = "{base_url}"\n'
    config_path.write_text(content)
