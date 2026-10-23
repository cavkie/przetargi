import httpx
import pytest

from przetargi.http import PoliteClient, RobotsDisallowed


def _client(handler):
    c = PoliteClient(min_delay=0)
    c._client = httpx.Client(transport=httpx.MockTransport(handler))
    return c


def _handler(request):
    if request.url.path == "/robots.txt":
        return httpx.Response(200, text="User-agent: *\nDisallow: /search\n",
                              headers={"content-type": "text/plain"})
    return httpx.Response(200, text="ok")


def test_robots_disallow_blocks_crawling():
    with pytest.raises(RobotsDisallowed):
        _client(_handler).get("https://example.org/search?q=x")


def test_documented_api_skips_robots():
    assert _client(_handler).get("https://example.org/search?q=x", api=True).text == "ok"
