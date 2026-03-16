"""Pydantic response models for the Monopigi API."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    import pandas
    import polars


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

    def to_polars(self) -> polars.DataFrame:
        """Convert results to a Polars DataFrame."""
        import polars as pl

        return pl.DataFrame([doc.model_dump() for doc in self.results])

    def to_pandas(self) -> pandas.DataFrame:
        """Convert results to a Pandas DataFrame."""
        import pandas as pd

        return pd.DataFrame([doc.model_dump() for doc in self.results])


class DocumentsResponse(BaseModel):
    """Response from /v1/{source}/documents."""

    source: str
    documents: list[Document]
    total: int
    limit: int
    offset: int
    message: str | None = None

    def to_polars(self) -> polars.DataFrame:
        """Convert results to a Polars DataFrame."""
        import polars as pl

        return pl.DataFrame([doc.model_dump() for doc in self.documents])

    def to_pandas(self) -> pandas.DataFrame:
        """Convert results to a Pandas DataFrame."""
        import pandas as pd

        return pd.DataFrame([doc.model_dump() for doc in self.documents])


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
