import json
import re

from przetargi.models import Offer, SourceStatus
from przetargi.render import FOOTER, maps_url, render_site, streetview_url

TODAY = "2026-10-23"


def mk(**kw):
    base = dict(source="um-gdansk", source_id="1", status="auction", type="flat", city="Gdańsk",
                address="ul. Ks. Mariana Góreckiego 8 lokal nr 3,4A", area_m2=94.47,
                start_price=720000, deposit=72000, auction_date="2026-10-26",
                auction_kind="przetarg ustny nieograniczony", notice_url="https://x/n.pdf",
                photo_url=None, raw_title="Gdańsk – Nowy Port", first_seen=TODAY, last_seen=TODAY)
    base.update(kw)
    return Offer(**base)


def _render(tmp_path, offers, statuses=()):
    render_site(offers, list(statuses), TODAY, tmp_path)
    return (tmp_path / "index.html").read_text(encoding="utf-8")


def _data(html):
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
    return json.loads(m.group(1))


def test_maps_url_encoding():
    assert maps_url(mk()) == (
        "https://www.google.com/maps/search/?api=1&query="
        "ul.%20Ks.%20Mariana%20G%C3%B3reckiego%208%20lokal%20nr%203%2C4A%2C%20Gda%C5%84sk"
    )


def test_streetview_fallback():
    assert streetview_url(mk()) is None
    assert streetview_url(mk(lat=54.4, lng=18.6)) == (
        "https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=54.4,18.6"
    )


def test_render_contains_rows_and_links(tmp_path):
    html = _render(tmp_path, {"k": mk()})
    assert FOOTER == "Szacunek, nie operat. Dane rynkowe: deweloperuch.pl (RCN). To nie jest porada finansowa."
    assert FOOTER in html
    for url in ("https://licytacje.komornik.pl", "https://elicytacje.mf.gov.pl",
                "https://krz.ms.gov.pl", "https://tabelaofert.pl"):
        assert url in html
    (row,) = _data(html)["offers"]
    assert row["maps"] == maps_url(mk()) and row["notice_url"] == "https://x/n.pdf"
    assert row["new"] is True and row["archived"] is False and row["price_per_m2"] == 7621


def test_archived_and_not_new(tmp_path):
    old = mk(auction_date="2026-10-01", first_seen="2026-09-01")
    (row,) = _data(_render(tmp_path, {"k": old}))["offers"]
    assert row["archived"] is True and row["new"] is False


def test_failed_source_shown(tmp_path):
    html = _render(tmp_path, {}, [SourceStatus("um-sopot", ok=False, count=0, at="2026-10-23 06:01",
                                               error="HTTPStatusError: 503")])
    assert "UM Sopot" in html and "HTTPStatusError: 503" in html


def test_data_is_escaped(tmp_path):
    html = _render(tmp_path, {"k": mk(raw_title="</script><script>alert(1)</script>")})
    assert "</script><script>alert(1)" not in html


def test_non_http_links_dropped(tmp_path):
    bad = mk(notice_url="javascript:alert(1)//cloudgdansk.pdf", photo_url="data:image/svg+xml,x")
    (row,) = _data(_render(tmp_path, {"k": bad}))["offers"]
    assert row["notice_url"] is None and row["photo_url"] is None
