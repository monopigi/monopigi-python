"""Tests for interactive browse feature."""


def test_check_textual_import() -> None:
    """Verify check_textual doesn't raise when textual is available."""
    from monopigi.browse import HAS_TEXTUAL, check_textual

    if HAS_TEXTUAL:
        check_textual()  # should not raise


def test_document_browser_init() -> None:
    """Test DocumentBrowser can be instantiated."""
    from monopigi.browse import HAS_TEXTUAL

    if not HAS_TEXTUAL:
        return  # skip if not installed
    from monopigi.browse import DocumentBrowser

    docs = [{"source": "ted", "title": "Test", "published_at": "2026-01-01", "quality_score": 0.9}]
    browser = DocumentBrowser(docs, source="ted")
    assert browser._documents == docs
