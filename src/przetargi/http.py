"""A slow, honest HTTP client: one User-Agent, per-host pauses, robots.txt."""
from __future__ import annotations

import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

USER_AGENT = "przetargi-monitor/1.0 (+https://github.com/cavkie/przetargi)"


class RobotsDisallowed(Exception):
    pass


class PoliteClient:
    def __init__(self, min_delay: float = 1.0, timeout: float = 60.0):
        self.min_delay = min_delay
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=timeout
        )
        self._last: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}

    def _wait(self, host: str) -> None:
        last = self._last.get(host)
        if last is not None:
            pause = self.min_delay - (time.monotonic() - last)
            if pause > 0:
                time.sleep(pause)
        self._last[host] = time.monotonic()

    def _allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            self._wait(parts.netloc)
            try:
                r = self._client.get(origin + "/robots.txt")
                if r.status_code == 200 and "text" in r.headers.get("content-type", "text"):
                    rp = RobotFileParser()
                    rp.parse(r.text.splitlines())
                    self._robots[origin] = rp
                else:
                    self._robots[origin] = None
            except httpx.HTTPError:
                self._robots[origin] = None
        rp = self._robots[origin]
        return rp is None or rp.can_fetch(USER_AGENT, url)

    def get(self, url: str, api: bool = False, **kwargs) -> httpx.Response:
        """api=True: a documented API whose usage policy allows our calls (robots.txt targets crawlers)."""
        if not api and not self._allowed(url):
            raise RobotsDisallowed(url)
        self._wait(urlsplit(url).netloc)
        r = self._client.get(url, **kwargs)
        r.raise_for_status()
        return r

    def get_bytes(self, url: str) -> bytes:
        return self.get(url).content
