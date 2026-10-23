from pathlib import Path

from przetargi.sources.amw import BASE, parse_detail, parse_list

FIX = Path(__file__).parent / "fixtures" / "amw"


def test_amw_list_keeps_sales_in_area():
    items = parse_list((FIX / "list.html").read_text(encoding="utf-8"), BASE)
    urls = [u for u, _ in items]
    assert all(u.startswith("https://amw.com.pl/pl/nieruchomosci/przetargi-nieruchomosci/") for u in urls)
    assert not any("slupsk" in u or "siemirowice" in u for u in urls)  # outside the area
    assert any("gdynia-ul-dembinskiego-11871" in u for u in urls)
    assert dict(items)[next(u for u in urls if "11871" in u)] == "Gdynia"


def test_amw_detail_land_is_not_residential():
    html = (FIX / "detail_gdynia_11871.html").read_text(encoding="utf-8")
    assert parse_detail(html, BASE + "/x-11871", "Gdynia") is None


def test_amw_detail_lease_is_skipped():
    html = (FIX / "detail_pruszcz_12346.html").read_text(encoding="utf-8")
    assert parse_detail(html, BASE + "/x-12346", "Pruszcz Gdański") is None


def test_amw_detail_flat_sale():
    html = """<main><h1>Gdynia ul. Morska 1 lokal nr 4</h1>
    Lokalizacja Woj.: pomorskie, Powiat: Gdynia, Gmina: Gdynia, ul. Morska 1
    Powierzchnia gruntu: ha użytkowa: 48,30 m 2 Kategoria mieszkanie
    Ogłoszenie o przetargu - Sprzedaż Przetarg w dniu: 23.11.2026r. godz. 11:00
    Pozycje przetargowe: Powierzchnia 48,30 m 2 Cena wywoławcza 390 000,00 PLN
    <img src="https://amw.com.pl/images_cache/amw_estate_image/amw/estates/a.jpg"></main>"""
    o = parse_detail(html, BASE + "/gdynia-ul-morska-1-999", "Gdynia")
    assert o.type == "flat" and o.status == "auction" and o.city == "Gdynia"
    assert o.start_price == 390000 and o.area_m2 == 48.3 and o.auction_date == "2026-11-23"
    assert o.address == "ul. Morska 1 lokal nr 4" and o.source_id == "999"
    assert o.photo_url == "https://amw.com.pl/images_cache/amw_estate_image/amw/estates/a.jpg"
