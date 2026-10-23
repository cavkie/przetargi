import json
from pathlib import Path

from przetargi.market import Stopped, apply_market, city_median
from przetargi.models import Offer

FIX = Path(__file__).parent / "fixtures" / "market"
VALUATION = json.loads((FIX / "valuation.json").read_text(encoding="utf-8"))
TRANSACTIONS = json.loads((FIX / "transactions_gdansk.json").read_text(encoding="utf-8"))
TODAY = "2026-10-23"


def mk(**kw):
    base = dict(source="um-gdansk", source_id="1", status="auction", type="flat", city="Gdańsk",
                address="ul. Uczniowska 37/4", area_m2=55.8, start_price=500000, deposit=None,
                auction_date="2026-10-26", auction_kind=None, notice_url="u", photo_url=None,
                raw_title="", lat=54.3935, lng=18.6415)
    base.update(kw)
    return Offer(**base)


class FakeCli:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def __call__(self, args):
        self.calls.append(args)
        if self.fail:
            raise Stopped("429")
        return VALUATION if args[0] == "valuation" else TRANSACTIONS


def test_city_median_period():
    assert city_median(TRANSACTIONS, TODAY) == (13512, "2026-07")
    assert city_median({**TRANSACTIONS, "last_complete_period": "2026-06"}, TODAY) == (13679, "2026-06")


def test_market_nearby_gap():
    offers = {"k": mk()}
    assert apply_market(offers, {}, cli=FakeCli(), today=TODAY) is None
    o = offers["k"]
    assert o.market_basis == "nearby"
    assert round(o.market_gap_pct, 1) == round((500000 / 941136 - 1) * 100, 1) == -46.9
    assert o.market_low_confidence is False and o.market_period == "24 mies."


def test_market_city_median_fallback():
    offers = {"k": mk(lat=None, lng=None)}
    apply_market(offers, {}, cli=FakeCli(), today=TODAY)
    o = offers["k"]
    assert o.market_basis == "city_median" and o.market_period == "2026-07"
    assert round(o.market_gap_pct, 1) == round((round(500000 / 55.8) / 13512 - 1) * 100, 1)


def test_market_houses_skipped():
    cli = FakeCli()
    offers = {"k": mk(type="house")}
    apply_market(offers, {}, cli=cli, today=TODAY)
    assert cli.calls == [] and offers["k"].market_gap_pct is None


def test_market_stop_halts_calls():
    cli = FakeCli(fail=True)
    offers = {"a": mk(), "b": mk(address="ul. Inna 1/1", lat=54.0)}
    assert apply_market(offers, {}, cli=cli, today=TODAY) == "market data unavailable"
    assert len(cli.calls) == 1
    assert offers["b"].market_gap_pct is None


def test_market_cache_hit_no_call():
    cache = {}
    apply_market({"k": mk()}, cache, cli=FakeCli(), today=TODAY)
    cli = FakeCli()
    offers = {"k": mk()}
    apply_market(offers, cache, cli=cli, today=TODAY)
    assert cli.calls == [] and offers["k"].market_basis == "nearby"


def test_market_low_confidence_flag():
    class LowCli(FakeCli):
        def __call__(self, args):
            return {**VALUATION, "low_confidence": True}

    offers = {"k": mk()}
    apply_market(offers, {}, cli=LowCli(), today=TODAY)
    assert offers["k"].market_low_confidence is True
