from __future__ import annotations

import pytest
import httpx

from rune.tools.fetch_url import fetch_url


# A known, simple, and stable URL for testing.
# Using a real, external URL makes the test less isolated, but for an
# end-to-end tool like this, it's often the most practical approach.
STABLE_URL = "https://httpbin.org/html"


@pytest.mark.asyncio
async def test_fetch_url_success():
    """Tests a successful visit to a simple HTML page."""
    result = await fetch_url(STABLE_URL)
    assert result.data["status"] == "success"
    assert "Herman Melville \\- Moby\\-Dick" in result.data["markdown_content"]


@pytest.mark.asyncio
async def test_fetch_url_http_error():
    """Tests that an HTTP status error (like 404) is raised correctly."""
    url_404 = "https://httpbin.org/status/404"
    with pytest.raises(ValueError, match=r"HTTP error (404|502)"):
        await fetch_url(url_404)


@pytest.mark.asyncio
async def test_fetch_url_request_error():
    """Tests that a network-level error is raised correctly."""
    invalid_url = "https://this-is-not-a-real-domain.invalid"
    with pytest.raises(ConnectionError, match="Network error visiting"):
        await fetch_url(invalid_url)


@pytest.mark.asyncio
async def test_fetch_url_timeout():
    """Tests that the timeout is correctly handled."""
    # This URL will take 10 seconds to respond.
    timeout_url = "https://httpbin.org/delay/10"
    with pytest.raises(ConnectionError, match="Network error visiting"):
        # We expect a timeout error, which is a type of RequestError -> ConnectionError
        await fetch_url(timeout_url, timeout=0.1)
