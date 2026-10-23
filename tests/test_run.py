import json

from przetargi.archive import load, save
from przetargi.models import Offer
from przetargi.run import run
from przetargi.sources import Source


def mk(source, address, **kw):
    base = dict(source=source, source_id=address, status="auction", type="flat", city="Gdańsk",
                address=address, area_m2=50.0, start_price=500000, deposit=None,
                auction_date="2026-12-01", auction_kind=None, notice_url="u", photo_url=None,
                raw_title="")
    base.update(kw)
    return Offer(**base)


def _boom(client):
    raise ValueError("layout changed")


def _run(tmp_path, sources, renders=None):
    return run(tmp_path / "data", tmp_path / "site", "2026-10-23", sources=sources,
               client=object(), geocode_lookup=lambda q: None, market_cli=lambda a: {},
               render=(lambda *a: renders.append(a)) if renders is not None else None)


def test_run_isolates_failing_source(tmp_path):
    save(tmp_path / "data" / "offers.json", {"a|old": mk("a", "old")})
    statuses = _run(tmp_path, [Source("a", _boom), Source("b", lambda c: [mk("b", "ul. Nowa 1/1")])], [])
    by = {s.source: s for s in statuses}
    assert by["a"].ok is False and "layout changed" in by["a"].error
    assert by["b"].ok is True and by["b"].count == 1
    offers = load(tmp_path / "data" / "offers.json")
    assert "a|old" in offers and "b|nowa 1/1" in offers


def test_zero_items_is_warning(tmp_path):
    (s,) = [x for x in _run(tmp_path, [Source("a", lambda c: [])], []) if x.source == "a"]
    assert s.ok is True and s.count == 0 and s.warning == "0 items: format changed?"


def test_zero_items_expected_no_warning(tmp_path):
    (s,) = [x for x in _run(tmp_path, [Source("a", lambda c: [], expect_items=False)], [])
            if x.source == "a"]
    assert s.ok is True and s.warning is None


def test_run_writes_files(tmp_path):
    renders = []
    _run(tmp_path, [Source("b", lambda c: [mk("b", "ul. Nowa 1/1")])], renders)
    for name in ("offers.json", "status.json", "geocode.json", "market.json"):
        assert (tmp_path / "data" / name).exists()
    status = json.loads((tmp_path / "data" / "status.json").read_text(encoding="utf-8"))
    assert status[0]["source"] == "b"
    assert len(renders) == 1


def test_market_stop_reported(tmp_path):
    from przetargi.market import Stopped

    def cli(args):
        raise Stopped("429")

    statuses = run(tmp_path / "data", tmp_path / "site", "2026-10-23",
                   sources=[Source("b", lambda c: [mk("b", "ul. Nowa 1/1")])], client=object(),
                   geocode_lookup=lambda q: (54.0, 18.0), market_cli=cli, render=lambda *a: None)
    (m,) = [s for s in statuses if s.source == "deweloperuch"]
    assert m.ok is False and m.warning == "market data unavailable"
