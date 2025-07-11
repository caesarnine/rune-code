from __future__ import annotations

import pytest
import httpx

from rune.tools.visit_url import visit_url


# A known, simple, and stable URL for testing.
# Using a real, external URL makes the test less isolated, but for an
# end-to-end tool like this, it's often the most practical approach.
STABLE_URL = "https://httpbin.org/html"


def test_visit_url_success():
    """Tests a successful visit to a simple HTML page."""
    result = visit_url(STABLE_URL)
    assert result.status == "success"
    assert "Herman Melville \\- Moby\\-Dick" in result.data["markdown_content"]


def test_visit_url_http_error():
    """Tests that an HTTP status error (like 404) is raised correctly."""
    url_404 = "https://httpbin.org/status/404"
    with pytest.raises(ValueError, match="HTTP error 404"):
        visit_url(url_404)


def test_visit_url_request_error():
    """Tests that a network-level error is raised correctly."""
    invalid_url = "https://this-is-not-a-real-domain.invalid"
    with pytest.raises(ConnectionError, match="Network error visiting"):
        visit_url(invalid_url)


def test_visit_url_timeout():
    """Tests that the timeout is correctly handled."""
    # This URL will take 10 seconds to respond.
    timeout_url = "https://httpbin.org/delay/10"
    with pytest.raises(ConnectionError, match="Network error visiting"):
        # We expect a timeout error, which is a type of RequestError -> ConnectionError
        visit_url(timeout_url, timeout=0.1)
