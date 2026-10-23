from przetargi.models import Offer
from przetargi.places import AREA, canonical_city


def test_canonical_city():
    assert canonical_city("GDANSK") == "Gdańsk"
    assert canonical_city("Pruszcz Gdański") == "Pruszcz Gdański"
    assert canonical_city("Słupsk") is None
    assert set(AREA) == {
        "Gdańsk", "Sopot", "Gdynia", "Pruszcz Gdański", "Kolbudy", "Żukowo", "Rumia",
    }


def test_offer_roundtrip_and_price_per_m2():
    o = Offer(source="um-gdansk", source_id="x", status="auction", type="flat",
              city="Gdańsk", address="Uczniowska 37/4", area_m2=48.0,
              start_price=500000, deposit=50000, auction_date="2026-10-26",
              auction_kind="przetarg ustny", notice_url="https://x", photo_url=None,
              raw_title="t")
    assert o.price_per_m2 == 10417
    assert Offer.from_dict(o.to_dict()) == o
