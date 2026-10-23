import json
import shutil
from pathlib import Path

import pytest

from przetargi.sources.sopot import (
    classify_title,
    doc_to_text,
    parse_article,
    parse_menu,
    parse_wykaz_attachments,
    wykaz_offer,
)
from przetargi.textutil import normalise_address

FIX = Path(__file__).parent / "fixtures" / "sopot"


def _read(name):
    return (FIX / name).read_text(encoding="utf-8")


def test_sopot_classify_titles():
    assert classify_title(
        "II publiczny przetarg ustny nieograniczony na sprzedaż lokalu mieszkalnego nr 1 położonego w budynku"
    ) == "sale"
    assert classify_title("Pisemny przetarg nieograniczony na najem lokalu użytkowego") == "skip"
    assert classify_title("(ROZSTRZYGNIĘTY) Przetarg ustny na sprzedaż lokalu mieszkalnego") == "skip"
    assert classify_title("Odwołanie przetargu na sprzedaż lokalu mieszkalnego nr 2") == "cancel"
    assert classify_title(
        "II publiczny przetarg ustny nieograniczony na sprzedaż lokalu niemieszkalnego nr 8"
    ) == "skip"
    assert classify_title("Przetarg ustny na sprzedaż nieruchomości gruntowej niezabudowanej") == "skip"


def test_sopot_menu_parses_ids():
    items = parse_menu(_read("menu107.json"))
    ids = [i for i, _ in items]
    assert 25322 in ids and len(items) == 50
    assert dict(items)[25322].startswith("II publiczny przetarg")


def test_sopot_article_25322():
    o = parse_article(_read("article25322.json"), _read("article25322.txt"))
    assert normalise_address(o.address) == "armii krajowej 61/1"
    assert o.type == "flat" and o.status == "auction" and o.city == "Sopot"
    assert o.auction_date == "2026-11-26"
    assert o.start_price == 850000 and o.area_m2 == 65.2 and o.deposit == 150000
    assert o.source == "um-sopot" and o.source_id == "25322"
    assert o.notice_url == "https://bip.sopot.pl/a,25322,ii-publiczny-przetarg-ustny-nieograniczony-na-sprzedaz-lokalu-mieszkalnego-nr-1-polozonego-w-budynku.html"


def test_sopot_address_with_staircase_note():
    from przetargi.sources.sopot import _address

    text = ("na sprzedaż lokalu mieszkalnego nr 3 położonego w budynku przy "
            "ul. Helskiej 9-11 (kl. 11) w Sopocie. Opis Nieruchomości: Nieruchomość przy ul. Helskiej 9-11")
    assert _address(text) == "ul. Helskiej 9-11/3"


def test_sopot_article_without_attachment_text():
    o = parse_article(_read("article25322.json"), None)
    assert normalise_address(o.address) == "armii krajowej 61/1"
    assert o.start_price is None and o.area_m2 is None


def test_sopot_wykaz_candidates_and_offer():
    cands = parse_wykaz_attachments(_read("article24519.json"))
    names = {aid for aid, _ in cands}
    assert 57962 in names and 57961 in names  # lokal wykazy at Armii Krajowej 61 and 74
    assert 57362 not in names  # dzierżawa of land
    assert 58639 not in names  # lokal użytkowy
    o = wykaz_offer(57962, dict(cands)[57962], _read("wykaz57962.txt"))
    assert o.status == "planned" and o.type == "flat"
    assert normalise_address(o.address) == "armii krajowej 61/1"
    assert o.start_price is None and o.auction_date is None


@pytest.mark.skipif(shutil.which("antiword") is None, reason="antiword not installed")
def test_doc_to_text_returns_none_on_garbage():
    assert doc_to_text(b"not a word document") is None
