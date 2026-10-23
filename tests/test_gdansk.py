from pathlib import Path

from przetargi.sources.gdansk import parse_article, parse_auction_pdf, parse_list
from przetargi.textutil import normalise_address

FIX = Path(__file__).parent / "fixtures" / "gdansk"
BASE = "https://gdansk.pl/urzad-miejski/ogloszenia-o-przetargach,a,1439"


def _by_street(offers, street):
    (o,) = [o for o in offers if street in normalise_address(o.address)]
    return o


def test_gdansk_pdf_finds_known_flats():
    offers = parse_auction_pdf((FIX / "2026-10-26.pdf").read_bytes(), "https://x/n.pdf")
    u = _by_street(offers, "uczniowska 37/4")
    assert u.start_price == 500000 and u.area_m2 == 55.8 and u.deposit == 50000
    assert _by_street(offers, "goreckiego 8/3,4a").start_price == 720000
    assert _by_street(offers, "lenartowicza 3/5").start_price == 300000
    for o in offers:
        assert o.status == "auction" and o.auction_date == "2026-10-26"
        assert o.type == "flat" and o.city == "Gdańsk" and o.source == "um-gdansk"
        assert o.auction_kind and "ustny" in o.auction_kind
        assert o.notice_url == "https://x/n.pdf"


def test_gdansk_pdf_keeps_only_residential():
    # each fixture has one land plot (dropped) and three flats
    a = parse_auction_pdf((FIX / "2026-10-26.pdf").read_bytes(), "https://x/a.pdf")
    b = parse_auction_pdf((FIX / "2026-11-30.pdf").read_bytes(), "https://x/b.pdf")
    assert len(a) == 3 and len(b) == 3
    assert not any("malczewskiego" in normalise_address(o.address) for o in a)
    assert _by_street(b, "wyspianskiego 15/4").start_price == 850000
    assert _by_street(b, "ceynowy 2/5").area_m2 == 16.5
    assert all(o.auction_date == "2026-11-30" for o in b)
    assert len({o.source_id for o in a + b}) == 6


def test_gdansk_list_and_article_links():
    links = parse_list((FIX / "list.html").read_text(encoding="utf-8"), BASE)
    assert len(links) == 2
    assert all("ogloszenie-o-przetargach" in u and ",a," in u for u in links)
    pdfs = parse_article((FIX / "article_3011.html").read_text(encoding="utf-8"), links[0])
    assert pdfs == [
        "https://download.cloudgdansk.pl/gdansk-pl/d/202609282580/ogloszenie-o-przetargach-nieograniczonych-planowanych-na-dzien-30-11-2026r-gazeta-wyborcza-z-dnia-23-09-2026r.pdf"
    ]


def test_gdansk_continuation_table_without_header():
    from przetargi.sources.gdansk import table_offers

    row = ["4.", "Gdańsk – Oliwa\nul. Leśna 2 lokal nr 7\nI piętro", "Działka nr 1",
           "40,00 m2", "400.000 zł", "40.000 zł", "Własność", "Lokal obejmujący 2 pokoje"]
    nxt = ["", "", "", "", "", "4.000 zł", "Przetarg ustny\nnieograniczony\ngodz. 11:00", ""]
    offers = table_offers([row, nxt], True, "2026-11-30", "https://x/c.pdf", "c")
    assert len(offers) == 1 and offers[0].start_price == 400000
    assert offers[0].auction_kind == "Przetarg ustny nieograniczony"
