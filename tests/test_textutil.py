from przetargi.textutil import (
    classify_type,
    is_cancellation,
    is_excluded_notice,
    normalise_address,
    parse_area,
    parse_date,
    parse_price,
)


def test_parse_numbers_and_dates():
    assert parse_price("1 250 000,00 zł") == 1250000
    assert parse_price("1 250 000 zł") == 1250000
    assert parse_price("500.000,00 zł") == 500000
    assert parse_price("brak") is None
    assert parse_area("48,37 m²") == 48.37
    assert parse_area("pow. użytkowa 61,2 m2") == 61.2
    assert parse_date("26 października 2026 r.") == "2026-10-26"
    assert parse_date("26.10.2026") == "2026-10-26"
    assert parse_date("dnia 3 listopada 2026") == "2026-11-03"


def test_normalise_address():
    assert normalise_address("ul. Uczniowska 37/4") == normalise_address("Uczniowska 37 lok. 4")
    assert normalise_address("ul. Góreckiego 8/3,4A") == "goreckiego 8/3,4a"
    assert normalise_address("Armii Krajowej 61 lokal nr 1") == "armii krajowej 61/1"


def test_classify_type():
    assert classify_type("sprzedaż lokalu mieszkalnego nr 4") == "flat"
    assert classify_type("spółdzielcze własnościowe prawo do lokalu") == "flat"
    assert classify_type("nieruchomość zabudowana budynkiem mieszkalnym jednorodzinnym") == "house"
    assert classify_type("lokal użytkowy") is None
    assert classify_type("nieruchomość niezabudowana") is None
    assert classify_type("garaż") is None


def test_notice_flags():
    assert is_excluded_notice("Przetarg na najem lokalu użytkowego")
    assert is_excluded_notice("PRZETARG ROZSTRZYGNIĘTY - lokal mieszkalny")
    assert is_excluded_notice("Informacja o wyniku przetargu")
    assert is_cancellation("Odwołanie przetargu na sprzedaż lokalu mieszkalnego")
    assert not is_excluded_notice(
        "II publiczny przetarg ustny nieograniczony na sprzedaż lokalu mieszkalnego"
    )
