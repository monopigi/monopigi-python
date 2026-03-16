"""Shared fixtures for SDK tests."""

import pytest


@pytest.fixture
def api_token() -> str:
    return "mp_live_testtoken1234567890abcdef"


@pytest.fixture
def base_url() -> str:
    return "https://api.monopigi.com"
