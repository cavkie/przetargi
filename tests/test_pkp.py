from pathlib import Path

from przetargi.sources.pkp import parse_list, parse_offer
from przetargi.textutil import normalise_address

FIX = Path(__file__).parent / "fixtures" / "pkp"


def _items():
    return parse_list((FIX / "list_pomorskie.html").read_text(encoding="utf-8"))


def test_pkp_list_finds_area_flats():
    items = _items()
    addrs = {normalise_address(i.address) for i in items}
    assert {"elblaska 89/1", "elblaska 89/2", "jana z kolna 29/1", "junacka 5/5"} <= addrs
    assert "osada kolejowa 13/1" in addrs  # Gdynia
    assert all(i.city in ("Gdańsk", "Gdynia", "Sopot", "Rumia", "Pruszcz Gdański", "Kolbudy", "Żukowo")
               for i in items)
    assert not any("dworcowa" in normalise_address(i.address) for i in items)  # "Pruszcz" 89-520 is not Pruszcz Gdański
    assert not any("kopernika" in normalise_address(i.address) for i in items)  # GRUNTY


def test_pkp_elblaska():
    (item,) = [i for i in _items() if i.id == "31786"]
    assert item.lat == 54.34931 and item.lng == 18.6825
    assert item.photo_url.startswith("https://www.pkp.pl/investments/31786/")
    o = parse_offer((FIX / "offer31786.html").read_text(encoding="utf-8"), item)
    assert o.start_price == 260000 and o.area_m2 == 110.72
    assert o.city == "Gdańsk" and o.type == "flat" and o.status == "auction"
    assert normalise_address(o.address) == "elblaska 89/1"
    assert o.auction_kind == "przetarg ustny nieograniczony"
    assert o.notice_url == "https://www.pkp.pl/pl/sprzedaz?menu=2&show=31786"
    assert o.lat == 54.34931 and o.photo_url == item.photo_url
