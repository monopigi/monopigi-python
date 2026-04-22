"""Tests for enterprise CLI commands (models, report, alert, monitor)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from monopigi.cli import app

runner = CliRunner()


def _mock_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text('token = "mp_live_test"\nbase_url = "https://test.example.com"\n')
    return config_path


def _make_client_mock() -> MagicMock:
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    return mock_client


# -- Models (no auth) ---------------------------------------------------------


def _make_httpx_response(payload: dict) -> MagicMock:
    """Build an httpx.Response-like mock that passes .raise_for_status() and .json()."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def test_models_command(tmp_path: Path) -> None:
    """'monopigi models' outputs model list in table format."""
    config_path = _mock_config(tmp_path)
    models_response = {
        "models": [
            {"id": "anthropic/claude-sonnet-4-20250514", "default": True},
            {"id": "mistral/mistral-large-latest", "default": False},
        ]
    }
    mock_resp = _make_httpx_response(models_response)

    with (
        patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path),
        patch("httpx.get", return_value=mock_resp),
    ):
        result = runner.invoke(app, ["models"])

    assert result.exit_code == 0
    assert "claude-sonnet" in result.stdout or "Model" in result.stdout


def test_models_command_json(tmp_path: Path) -> None:
    """'monopigi models --format json' outputs JSON."""
    config_path = _mock_config(tmp_path)
    models_response = {
        "models": [
            {"id": "anthropic/claude-sonnet-4-20250514", "default": True},
        ]
    }
    mock_resp = _make_httpx_response(models_response)

    with (
        patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path),
        patch("httpx.get", return_value=mock_resp),
    ):
        result = runner.invoke(app, ["models", "--format", "json"])

    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert "models" in parsed


# -- Report commands -----------------------------------------------------------


def test_report_create(tmp_path: Path) -> None:
    """'monopigi report create 123 --type afm' calls create_report on the client."""
    config_path = _mock_config(tmp_path)
    mock_client = _make_client_mock()
    mock_client.create_report.return_value = {"id": "rpt-001", "status": "pending"}

    with (
        patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path),
        patch("monopigi.cli._get_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["report", "create", "123", "--type", "afm"])

    assert result.exit_code == 0
    mock_client.create_report.assert_called_once_with("123", identifier_type="afm")
    assert "rpt-001" in result.stdout


def test_report_list(tmp_path: Path) -> None:
    """'monopigi report list' outputs a table of reports."""
    config_path = _mock_config(tmp_path)
    mock_client = _make_client_mock()
    mock_client.list_reports.return_value = {
        "items": [
            {
                "id": "rpt-001",
                "entity_identifier": "123",
                "identifier_type": "afm",
                "status": "completed",
                "created_at": "2026-03-24",
            }
        ],
        "total": 1,
    }

    with (
        patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path),
        patch("monopigi.cli._get_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["report", "list"])

    assert result.exit_code == 0
    mock_client.list_reports.assert_called_once_with(limit=20)
    assert "rpt-001" in result.stdout


def test_report_get(tmp_path: Path) -> None:
    """'monopigi report get <id>' calls get_report and outputs JSON."""
    config_path = _mock_config(tmp_path)
    mock_client = _make_client_mock()
    report_data = {"id": "rpt-001", "status": "completed", "entity_identifier": "123"}
    mock_client.get_report.return_value = report_data

    with (
        patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path),
        patch("monopigi.cli._get_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["report", "get", "rpt-001"])

    assert result.exit_code == 0
    mock_client.get_report.assert_called_once_with("rpt-001")
    parsed = json.loads(result.stdout)
    assert parsed["id"] == "rpt-001"


# -- Alert commands ------------------------------------------------------------


def test_alert_create(tmp_path: Path) -> None:
    """'monopigi alert create "Test" --keywords software' builds correct filters."""
    config_path = _mock_config(tmp_path)
    mock_client = _make_client_mock()
    mock_client.create_alert_profile.return_value = {"id": "alert-001"}

    with (
        patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path),
        patch("monopigi.cli._get_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["alert", "create", "Test Alert", "--keywords", "software,IT"])

    assert result.exit_code == 0
    call_args = mock_client.create_alert_profile.call_args
    assert call_args[0][0] == "Test Alert"
    filters = call_args[0][1]
    assert filters["keywords"] == ["software", "IT"]
    assert "alert-001" in result.stdout


def test_alert_create_with_sources_and_value(tmp_path: Path) -> None:
    """Alert create with --sources and --min-value passes correct filters."""
    config_path = _mock_config(tmp_path)
    mock_client = _make_client_mock()
    mock_client.create_alert_profile.return_value = {"id": "alert-002"}

    with (
        patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path),
        patch("monopigi.cli._get_client", return_value=mock_client),
    ):
        result = runner.invoke(
            app, ["alert", "create", "Big Tenders", "--sources", "ted,diavgeia", "--min-value", "100000"]
        )

    assert result.exit_code == 0
    call_args = mock_client.create_alert_profile.call_args
    filters = call_args[0][1]
    assert filters["sources"] == ["ted", "diavgeia"]
    assert filters["min_value"] == 100000.0


def test_alert_list(tmp_path: Path) -> None:
    """'monopigi alert list' outputs alert profiles."""
    config_path = _mock_config(tmp_path)
    mock_client = _make_client_mock()
    mock_client.list_alert_profiles.return_value = {
        "items": [{"id": "alert-001", "name": "IT Tenders", "is_active": True, "created_at": "2026-03-24"}],
        "total": 1,
    }

    with (
        patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path),
        patch("monopigi.cli._get_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["alert", "list"])

    assert result.exit_code == 0
    mock_client.list_alert_profiles.assert_called_once_with(limit=20)
    assert "IT Tenders" in result.stdout


def test_alert_delete(tmp_path: Path) -> None:
    """'monopigi alert delete <id>' calls delete_alert_profile."""
    config_path = _mock_config(tmp_path)
    mock_client = _make_client_mock()
    mock_client.delete_alert_profile.return_value = {"status": "deleted"}

    with (
        patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path),
        patch("monopigi.cli._get_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["alert", "delete", "alert-001"])

    assert result.exit_code == 0
    mock_client.delete_alert_profile.assert_called_once_with("alert-001")


def test_alert_deliveries(tmp_path: Path) -> None:
    """'monopigi alert deliveries' lists deliveries."""
    config_path = _mock_config(tmp_path)
    mock_client = _make_client_mock()
    mock_client.list_alert_deliveries.return_value = {
        "items": [{"id": "del-001", "channel": "email", "delivery_status": "sent", "delivered_at": "2026-03-24"}],
        "total": 1,
    }

    with (
        patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path),
        patch("monopigi.cli._get_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["alert", "deliveries"])

    assert result.exit_code == 0
    mock_client.list_alert_deliveries.assert_called_once_with(profile_id=None, limit=20)


# -- Monitor commands ----------------------------------------------------------


def test_monitor_add(tmp_path: Path) -> None:
    """'monopigi monitor add 123 --type afm --label Test' calls add_monitored_entity."""
    config_path = _mock_config(tmp_path)
    mock_client = _make_client_mock()
    mock_client.add_monitored_entity.return_value = {
        "id": "mon-001",
        "entity_identifier": "123",
        "label": "Test",
    }

    with (
        patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path),
        patch("monopigi.cli._get_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["monitor", "add", "123", "--type", "afm", "--label", "Test"])

    assert result.exit_code == 0
    mock_client.add_monitored_entity.assert_called_once_with("123", identifier_type="afm", label="Test")
    assert "123" in result.stdout


def test_monitor_add_no_label(tmp_path: Path) -> None:
    """Without --label, label=None is passed to the client."""
    config_path = _mock_config(tmp_path)
    mock_client = _make_client_mock()
    mock_client.add_monitored_entity.return_value = {"id": "mon-002", "entity_identifier": "456"}

    with (
        patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path),
        patch("monopigi.cli._get_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["monitor", "add", "456"])

    assert result.exit_code == 0
    mock_client.add_monitored_entity.assert_called_once_with("456", identifier_type="afm", label=None)


def test_monitor_list(tmp_path: Path) -> None:
    """'monopigi monitor list' outputs monitored entities table."""
    config_path = _mock_config(tmp_path)
    mock_client = _make_client_mock()
    mock_client.list_monitored_entities.return_value = {
        "items": [
            {
                "id": "mon-001",
                "entity_identifier": "099369820",
                "identifier_type": "afm",
                "label": "ACME Corp",
                "last_checked_at": "2026-03-24",
            }
        ],
        "total": 1,
    }

    with (
        patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path),
        patch("monopigi.cli._get_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["monitor", "list"])

    assert result.exit_code == 0
    mock_client.list_monitored_entities.assert_called_once_with(limit=20)
    assert "099369820" in result.stdout


def test_monitor_remove(tmp_path: Path) -> None:
    """'monopigi monitor remove <id>' calls remove_monitored_entity."""
    config_path = _mock_config(tmp_path)
    mock_client = _make_client_mock()
    mock_client.remove_monitored_entity.return_value = {"status": "deactivated"}

    with (
        patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path),
        patch("monopigi.cli._get_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["monitor", "remove", "mon-001"])

    assert result.exit_code == 0
    mock_client.remove_monitored_entity.assert_called_once_with("mon-001")


def test_monitor_events(tmp_path: Path) -> None:
    """'monopigi monitor events' lists monitoring events."""
    config_path = _mock_config(tmp_path)
    mock_client = _make_client_mock()
    mock_client.list_entity_events.return_value = {
        "items": [
            {
                "id": "evt-001",
                "event_type": "new_decision",
                "document_source_id": "diavgeia:ABC",
                "summary": "New decision published",
                "detected_at": "2026-03-24",
                "acknowledged_at": None,
            }
        ],
        "total": 1,
    }

    with (
        patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path),
        patch("monopigi.cli._get_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["monitor", "events"])

    assert result.exit_code == 0
    mock_client.list_entity_events.assert_called_once_with(entity_id=None, event_type=None, limit=20)
    assert "new_decision" in result.stdout


def test_monitor_events_with_filters(tmp_path: Path) -> None:
    """'monopigi monitor events --entity-id <id> --type <type>' passes filters."""
    config_path = _mock_config(tmp_path)
    mock_client = _make_client_mock()
    mock_client.list_entity_events.return_value = {"items": [], "total": 0}

    with (
        patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path),
        patch("monopigi.cli._get_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["monitor", "events", "--entity-id", "mon-001", "--type", "new_contract"])

    assert result.exit_code == 0
    mock_client.list_entity_events.assert_called_once_with(entity_id="mon-001", event_type="new_contract", limit=20)


def test_monitor_report(tmp_path: Path) -> None:
    """'monopigi monitor report <id>' calls entity_health_report."""
    config_path = _mock_config(tmp_path)
    mock_client = _make_client_mock()
    mock_client.entity_health_report.return_value = {
        "report_id": "hr-001",
        "entity_identifier": "099369820",
        "status": "generating",
    }

    with (
        patch("monopigi.cli.DEFAULT_CONFIG_PATH", config_path),
        patch("monopigi.cli._get_client", return_value=mock_client),
    ):
        result = runner.invoke(app, ["monitor", "report", "mon-001"])

    assert result.exit_code == 0
    mock_client.entity_health_report.assert_called_once_with("mon-001")
    assert "hr-001" in result.stdout
