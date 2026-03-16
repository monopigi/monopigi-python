"""Tests for the Monopigi CLI."""

from pathlib import Path
from unittest.mock import patch

from monopigi_sdk.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_auth_login(tmp_path: Path):
    config_path = tmp_path / "config.toml"
    with patch("monopigi_sdk.cli.DEFAULT_CONFIG_PATH", config_path):
        result = runner.invoke(app, ["auth", "login", "mp_live_testtoken123"])
    assert result.exit_code == 0
    assert "saved" in result.stdout.lower() or "authenticated" in result.stdout.lower()


def test_auth_login_no_token():
    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code != 0


def test_auth_status_no_config(tmp_path: Path):
    config_path = tmp_path / "nonexistent.toml"
    with patch("monopigi_sdk.cli.DEFAULT_CONFIG_PATH", config_path):
        result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 0
    assert "not configured" in result.stdout.lower() or "no token" in result.stdout.lower()


def test_sources_requires_auth(tmp_path: Path):
    config_path = tmp_path / "nonexistent.toml"
    with patch("monopigi_sdk.cli.DEFAULT_CONFIG_PATH", config_path):
        result = runner.invoke(app, ["sources"])
    assert result.exit_code != 0 or "no api token" in result.stdout.lower()
