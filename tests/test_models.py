"""Tests for SDK models and exceptions."""

from monopigi_sdk.exceptions import AuthError, MonopigiError, NotFoundError, RateLimitError
from monopigi_sdk.models import (
    Document,
    DocumentsResponse,
    OutputFormat,
    SearchResponse,
    Source,
    SourceStatus,
    StatsResponse,
    Tier,
    UsageResponse,
)


def test_monopigi_error_is_base() -> None:
    err = MonopigiError("something broke")
    assert str(err) == "something broke"
    assert isinstance(err, Exception)


def test_auth_error_inherits() -> None:
    err = AuthError("bad token")
    assert isinstance(err, MonopigiError)


def test_rate_limit_error_has_reset() -> None:
    err = RateLimitError("over quota", reset_at="2026-03-16T00:00:00Z")
    assert err.reset_at == "2026-03-16T00:00:00Z"
    assert isinstance(err, MonopigiError)


def test_not_found_error() -> None:
    err = NotFoundError("unknown source: foo")
    assert isinstance(err, MonopigiError)


def test_source_status_enum() -> None:
    assert SourceStatus.ACTIVE == "active"
    assert SourceStatus.UNAVAILABLE == "unavailable"
    assert SourceStatus("active") == SourceStatus.ACTIVE


def test_tier_enum() -> None:
    assert Tier.FREE == "free"
    assert Tier.PRO == "pro"
    assert Tier.ENTERPRISE == "enterprise"


def test_output_format_enum() -> None:
    assert OutputFormat.TABLE == "table"
    assert OutputFormat.JSON == "json"
    assert OutputFormat.CSV == "csv"


def test_source_model() -> None:
    src = Source(name="ted", label="TED (EU)", status="active", description="EU procurement")
    assert src.name == "ted"
    assert src.status == SourceStatus.ACTIVE


def test_document_model() -> None:
    doc = Document(
        source_id="ted:123-2024",
        source="ted",
        title="Medical equipment procurement",
        published_at="2026-02-18",
        source_url="https://ted.europa.eu/en/notice/123-2024/html",
        language="el",
        quality_score=0.85,
    )
    assert doc.source == "ted"
    assert doc.quality_score == 0.85


def test_search_response() -> None:
    resp = SearchResponse(query="hospital", results=[], total=0, limit=100, offset=0)
    assert resp.total == 0


def test_stats_response() -> None:
    resp = StatsResponse(total_documents=18849, sources={})
    assert resp.total_documents == 18849


def test_usage_response_accepts_string_tier() -> None:
    resp = UsageResponse(tier="free", daily_quota=10, daily_used=3, daily_remaining=7, reset_at="2026-03-17T00:00:00Z")
    assert resp.tier == Tier.FREE
    assert resp.daily_remaining == 7


# --- DataFrame conversion tests ---

_SAMPLE_DOCS = [
    {
        "source_id": "ted-123",
        "source": "ted",
        "title": "Hospital procurement",
        "doc_type": "contract",
    },
    {
        "source_id": "ted-456",
        "source": "ted",
        "title": "Medical supplies",
        "doc_type": "notice",
    },
]


def test_search_response_to_polars() -> None:
    import polars as pl

    resp = SearchResponse(query="hospital", results=_SAMPLE_DOCS, total=2, limit=100, offset=0)
    df = resp.to_polars()
    assert isinstance(df, pl.DataFrame)
    assert len(df) == 2
    assert "source_id" in df.columns


def test_documents_response_to_polars() -> None:
    import polars as pl

    resp = DocumentsResponse(source="ted", documents=_SAMPLE_DOCS, total=2, limit=100, offset=0)
    df = resp.to_polars()
    assert isinstance(df, pl.DataFrame)
    assert len(df) == 2
    assert "source_id" in df.columns


def test_search_response_to_pandas() -> None:
    import pandas as pd

    resp = SearchResponse(query="hospital", results=_SAMPLE_DOCS, total=2, limit=100, offset=0)
    df = resp.to_pandas()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "source_id" in df.columns


def test_documents_response_to_pandas() -> None:
    import pandas as pd

    resp = DocumentsResponse(source="ted", documents=_SAMPLE_DOCS, total=2, limit=100, offset=0)
    df = resp.to_pandas()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "source_id" in df.columns
