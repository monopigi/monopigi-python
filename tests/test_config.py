"""Tests for config/token storage."""

from pathlib import Path

from monopigi_sdk.config import Config, load_config, save_config


def test_save_and_load_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    save_config("mp_live_abc123", base_url="https://api.monopigi.com", config_path=config_path)
    cfg = load_config(config_path=config_path)
    assert isinstance(cfg, Config)
    assert cfg.token == "mp_live_abc123"
    assert cfg.base_url == "https://api.monopigi.com"


def test_load_missing_config(tmp_path: Path) -> None:
    config_path = tmp_path / "nonexistent.toml"
    cfg = load_config(config_path=config_path)
    assert cfg.token == ""
    assert cfg.base_url == "https://api.monopigi.com"


def test_save_overwrites(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    save_config("token_1", config_path=config_path)
    save_config("token_2", config_path=config_path)
    cfg = load_config(config_path=config_path)
    assert cfg.token == "token_2"


def test_escapes_special_characters(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    save_config('token_with"quotes', config_path=config_path)
    cfg = load_config(config_path=config_path)
    assert cfg.token == 'token_with"quotes'
