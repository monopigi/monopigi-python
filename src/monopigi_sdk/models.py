"""Pydantic response models for the Monopigi API."""

from enum import StrEnum

from pydantic import BaseModel


class SourceStatus(StrEnum):
    """Status of a data source."""

    ACTIVE = "active"
    UNAVAILABLE = "unavailable"
    PLANNED = "planned"


class Tier(StrEnum):
    """API subscription tier."""

    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class OutputFormat(StrEnum):
    """CLI output format."""

    TABLE = "table"
    JSON = "json"
    CSV = "csv"


class Source(BaseModel):
    """A data source available through Monopigi."""

    name: str
    label: str
    status: SourceStatus
    description: str


class Document(BaseModel):
    """A document from the curated data layer."""

    source_id: str
    source: str
    title: str | None = None
    doc_type: str | None = None
    doc_category: str | None = None
    published_at: str | None = None
    source_url: str | None = None
    language: str | None = None
    quality_score: float | None = None


class SearchResponse(BaseModel):
    """Response from /v1/search."""

    query: str
    results: list[Document]
    total: int
    limit: int
    offset: int
    message: str | None = None


class DocumentsResponse(BaseModel):
    """Response from /v1/{source}/documents."""

    source: str
    documents: list[Document]
    total: int
    limit: int
    offset: int
    message: str | None = None


class SourceStats(BaseModel):
    """Per-source statistics."""

    documents: int
    last_updated: str | None = None
    avg_quality: float | None = None


class StatsResponse(BaseModel):
    """Response from /v1/stats."""

    total_documents: int
    sources: dict[str, SourceStats] = {}
    message: str | None = None


class UsageResponse(BaseModel):
    """Response from /v1/usage."""

    tier: Tier
    daily_quota: int
    daily_used: int
    daily_remaining: int
    reset_at: str
