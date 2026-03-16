"""Tests for SDK models and exceptions."""

from monopigi_sdk.exceptions import AuthError, MonopigiError, NotFoundError, RateLimitError
from monopigi_sdk.models import Document, SearchResponse, Source, StatsResponse, UsageResponse


def test_monopigi_error_is_base():
    err = MonopigiError("something broke")
    assert str(err) == "something broke"
    assert isinstance(err, Exception)


def test_auth_error_inherits():
    err = AuthError("bad token")
    assert isinstance(err, MonopigiError)


def test_rate_limit_error_has_reset():
    err = RateLimitError("over quota", reset_at="2026-03-16T00:00:00Z")
    assert err.reset_at == "2026-03-16T00:00:00Z"
    assert isinstance(err, MonopigiError)


def test_not_found_error():
    err = NotFoundError("unknown source: foo")
    assert isinstance(err, MonopigiError)


def test_source_model():
    src = Source(name="ted", label="TED (EU)", status="active", description="EU procurement")
    assert src.name == "ted"
    assert src.status == "active"


def test_document_model():
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


def test_search_response():
    resp = SearchResponse(
        query="hospital",
        results=[],
        total=0,
        limit=100,
        offset=0,
    )
    assert resp.total == 0
    assert resp.results == []


def test_stats_response():
    resp = StatsResponse(total_documents=18849, sources={})
    assert resp.total_documents == 18849


def test_usage_response():
    resp = UsageResponse(tier="free", daily_quota=10, daily_used=3, daily_remaining=7, reset_at="2026-03-17T00:00:00Z")
    assert resp.daily_remaining == 7
