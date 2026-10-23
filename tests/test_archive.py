from przetargi.archive import is_archived, load, merge, offer_key, save
from przetargi.models import Offer


def mk(**kw) -> Offer:
    base = dict(source="um-gdansk", source_id="n1", status="auction", type="flat",
                city="Gdańsk", address="ul. Uczniowska 37/4", area_m2=48.0,
                start_price=500000, deposit=50000, auction_date="2026-10-26",
                auction_kind="przetarg ustny", notice_url="https://x/1.pdf",
                photo_url=None, raw_title="t")
    base.update(kw)
    return Offer(**base)


def test_merge_new_offer():
    out = merge({}, [mk()], "2026-10-23")
    (o,) = out.values()
    assert o.first_seen == o.last_seen == "2026-10-23"
    assert len(o.price_history) == 1 and o.price_history[0].start_price == 500000


def test_merge_second_round_lower_price():
    a = merge({}, [mk()], "2026-10-23")
    b = merge(a, [mk(status="rokowania", start_price=400000, source_id="n2",
                     address="Uczniowska 37 lok. 4", auction_date="2026-12-10",
                     notice_url="https://x/2.pdf")], "2026-11-20")
    assert len(b) == 1
    (o,) = b.values()
    assert len(o.price_history) == 2
    assert o.price_drop is True
    assert o.first_seen == "2026-10-23"
    assert o.status == "rokowania" and o.start_price == 400000


def test_merge_planned_then_auction():
    a = merge({}, [mk(status="planned", start_price=None, auction_date=None)], "2026-10-01")
    b = merge(a, [mk(start_price=300000)], "2026-10-23")
    (o,) = b.values()
    assert o.status == "auction" and o.start_price == 300000


def test_merge_auction_not_downgraded_by_wykaz():
    a = merge({}, [mk()], "2026-10-23")
    b = merge(a, [mk(status="planned", start_price=None, auction_date=None)], "2026-10-24")
    (o,) = b.values()
    assert o.status == "auction" and o.start_price == 500000
    assert o.auction_date == "2026-10-26"


def test_merge_cancellation():
    a = merge({}, [mk()], "2026-10-20")
    b = merge(a, [mk(status="cancelled", start_price=None)], "2026-10-21")
    (o,) = b.values()
    assert o.status == "cancelled"
    assert is_archived(o, "2026-10-21")


def test_is_archived_rules():
    assert is_archived(mk(auction_date="2026-10-22", last_seen="2026-10-23"), "2026-10-23")
    assert not is_archived(mk(auction_date="2026-10-26", last_seen="2026-10-23"), "2026-10-23")
    assert is_archived(mk(auction_date=None, last_seen="2026-10-08"), "2026-10-23")
    assert not is_archived(mk(auction_date=None, last_seen="2026-10-10"), "2026-10-23")


def test_offer_key_falls_back_to_source_id():
    assert offer_key(mk(source="pkp", address="", source_id="77")) == "pkp|77"
    assert offer_key(mk()) == "um-gdansk|uczniowska 37/4"


def test_save_load_roundtrip(tmp_path):
    a = merge({}, [mk()], "2026-10-23")
    p = tmp_path / "offers.json"
    save(p, a)
    assert load(p) == a
    assert load(tmp_path / "missing.json") == {}
