"""Tests for the Monopigi CLI."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from monopigi.cli import _filter_fields, app
from monopigi.models import OutputFormat

runner = CliRunner()


def test_auth_login(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    with patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path):
        result = runner.invoke(app, ["auth", "login", "mp_live_testtoken123"])
    assert result.exit_code == 0
    assert "saved" in result.stdout.lower() or "authenticated" in result.stdout.lower()


def test_auth_login_no_token() -> None:
    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 0  # shows help instead of error
    assert "TOKEN" in result.output


def test_auth_status_no_config(tmp_path: Path) -> None:
    config_path = tmp_path / "nonexistent.toml"
    with patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path):
        result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 0
    assert "not configured" in result.stdout.lower() or "no token" in result.stdout.lower()


def test_sources_requires_auth(tmp_path: Path) -> None:
    config_path = tmp_path / "nonexistent.toml"
    with patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path):
        result = runner.invoke(app, ["sources"])
    assert result.exit_code != 0 or "no api token" in result.stdout.lower()


def test_filter_fields_selects_subset() -> None:
    doc = {"source": "ted", "title": "Hospital", "date": "2026-01-01", "score": 0.9}
    result = _filter_fields(doc, "source,title")
    assert result == {"source": "ted", "title": "Hospital"}


def test_filter_fields_none_returns_all() -> None:
    doc = {"source": "ted", "title": "Hospital"}
    result = _filter_fields(doc, None)
    assert result == doc


def test_output_format_jsonl_exists() -> None:
    assert OutputFormat.JSONL == "jsonl"


def test_search_count_flag(tmp_path: Path) -> None:
    """--count flag should print just the total number."""
    config_path = tmp_path / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text('token = "mp_live_test"\nbase_url = "https://test.example.com"\n')

    mock_resp = MagicMock()
    mock_resp.total = 42
    mock_resp.results = []

    mock_client = MagicMock()
    mock_client.search.return_value = mock_resp
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with (
        patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path),
        patch("monopigi.cli._get_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["search", "hospital", "--count"])

    assert result.exit_code == 0
    assert "42" in result.stdout


def test_search_fields_flag(tmp_path: Path) -> None:
    """--fields flag should filter output columns."""
    config_path = tmp_path / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text('token = "mp_live_test"\nbase_url = "https://test.example.com"\n')

    mock_doc = MagicMock()
    mock_doc.model_dump.return_value = {
        "source_id": "ted:123",
        "source": "ted",
        "title": "Hospital",
        "quality_score": 0.9,
    }
    mock_doc.source = "ted"
    mock_doc.title = "Hospital"
    mock_doc.published_at = None
    mock_doc.quality_score = 0.9

    mock_resp = MagicMock()
    mock_resp.total = 1
    mock_resp.results = [mock_doc]

    mock_client = MagicMock()
    mock_client.search.return_value = mock_resp
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with (
        patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path),
        patch("monopigi.cli._get_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["search", "hospital", "--fields", "source,title", "--format", "json"])

    assert result.exit_code == 0
    assert "source" in result.stdout
    assert "title" in result.stdout
    # Should NOT include quality_score since we filtered to source,title
    assert "quality_score" not in result.stdout


def test_config_set_and_get(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    with patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path):
        result = runner.invoke(app, ["config", "set", "cache_ttl", "600"])
    assert result.exit_code == 0
    assert "cache_ttl" in result.stdout


def test_config_set_invalid_key(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    with patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path):
        result = runner.invoke(app, ["config", "set", "invalid_key", "value"])
    assert result.exit_code != 0


def test_config_list(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text('token = "mp_live_test"\nbase_url = "https://api.monopigi.com"\n')
    with patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path):
        result = runner.invoke(app, ["config", "list"])
    assert result.exit_code == 0
    assert "token" in result.stdout
    assert "base_url" in result.stdout
