from przetargi.geocode import geocode_all, query_for
from przetargi.models import Offer


def mk(address="ul. Uczniowska 37/4", lat=None):
    return Offer(source="um-gdansk", source_id="1", status="auction", type="flat",
                 city="Gdańsk", address=address, area_m2=None, start_price=None, deposit=None,
                 auction_date=None, auction_kind=None, notice_url="u", photo_url=None,
                 raw_title="", lat=lat, lng=lat)


def test_query_drops_flat_number():
    assert query_for(mk("ul. Uczniowska 37 lokal nr 4")) == "Uczniowska 37, Gdańsk, Polska"
    assert query_for(mk("ul. Uczniowska 37/4")) == "Uczniowska 37, Gdańsk, Polska"


def test_geocode_uses_cache():
    calls = []
    offers = {"a": mk()}
    cache = {query_for(offers["a"]): [54.4, 18.6]}
    geocode_all(offers, cache, lambda q: calls.append(q))
    assert calls == [] and offers["a"].lat == 54.4 and offers["a"].lng == 18.6


def test_geocode_caches_miss():
    calls = []
    offers = {"a": mk()}
    cache = {}
    geocode_all(offers, cache, lambda q: calls.append(q) or None)
    geocode_all(offers, cache, lambda q: calls.append(q) or None)
    assert len(calls) == 1 and cache[query_for(offers["a"])] is None and offers["a"].lat is None


def test_geocode_skips_known_and_empty():
    calls = []
    offers = {"a": mk(lat=54.0), "b": mk(address="")}
    geocode_all(offers, {}, lambda q: calls.append(q))
    assert calls == []
