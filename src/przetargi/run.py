"""The daily run: fetch every source, merge, geocode, compare with the market, render."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import archive
from .geocode import geocode_all, nominatim_lookup
from .http import PoliteClient
from .market import UNAVAILABLE, apply_market, run_cli
from .models import SourceStatus
from .sources import SOURCES

TZ = ZoneInfo("Europe/Warsaw")


def _now() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M")


def _read_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                    encoding="utf-8")


def run(data_dir: Path, site_dir: Path, today: str, sources=SOURCES, client=None,
        geocode_lookup=None, market_cli=None, render=None) -> list[SourceStatus]:
    data_dir, site_dir = Path(data_dir), Path(site_dir)
    client = client or PoliteClient()
    offers = archive.load(data_dir / "offers.json")
    statuses: list[SourceStatus] = []

    for src in sources:
        try:
            fetched = src.fetch(client)
        except Exception as e:  # one broken source must not stop the others
            statuses.append(SourceStatus(src.name, ok=False, count=0, at=_now(),
                                         error=f"{type(e).__name__}: {e}"[:300]))
            continue
        offers = archive.merge(offers, fetched, today)
        statuses.append(SourceStatus(src.name, ok=True, count=len(fetched), at=_now(),
                                     warning=None if fetched or not src.expect_items
                                     else "0 items: format changed?"))

    archive.save(data_dir / "offers.json", offers)

    geocache = _read_json(data_dir / "geocode.json", {})
    try:
        geocode_all(offers, geocache, geocode_lookup or nominatim_lookup(client))
    except Exception as e:
        statuses.append(SourceStatus("nominatim", ok=False, count=0, at=_now(), error=str(e)[:300]))
    _write_json(data_dir / "geocode.json", geocache)

    market_cache = _read_json(data_dir / "market.json", {})
    stop_file = data_dir / "market_stop.json"  # a STOP is lifted only by a person deleting it
    error = None
    if stop_file.exists():
        warning = UNAVAILABLE
    else:
        try:
            warning = apply_market(offers, market_cache, cli=market_cli or run_cli, today=today)
        except Exception as e:  # market data is optional; the page must still be built
            warning, error = UNAVAILABLE, f"{type(e).__name__}: {e}"[:300]
        if warning == UNAVAILABLE and error is None:
            _write_json(stop_file, {"at": _now(), "reason": "deweloperuch STOP (exit code 3)"})
    statuses.append(SourceStatus("deweloperuch", ok=warning is None, count=0, at=_now(),
                                 warning=warning, error=error))
    _write_json(data_dir / "market.json", market_cache)

    archive.save(data_dir / "offers.json", offers)
    _write_json(data_dir / "status.json", [asdict(s) for s in statuses])

    if render is None:
        from .render import render_site as render
    render(offers, statuses, today, site_dir)
    return statuses


def main() -> None:
    root = Path.cwd()
    statuses = run(root / "data", root / "site", datetime.now(TZ).date().isoformat())
    for s in statuses:
        print(f"{s.source:14} {'ok ' if s.ok else 'ERR'} {s.count:4} {s.error or s.warning or ''}")


if __name__ == "__main__":
    main()
