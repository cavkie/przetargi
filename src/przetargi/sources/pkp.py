"""PKP S.A. property sales: every offer is in a GeoJSON blob on the listing page."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote

from bs4 import BeautifulSoup

from ..http import PoliteClient
from ..models import Offer
from ..places import canonical_city
from ..textutil import classify_type, fold, parse_area, parse_date, parse_price, parse_share

NAME = "pkp"
SITE = "https://www.pkp.pl"
LIST_URL = f"{SITE}/pl/sprzedaz?menu=2&province_id=11&category1_id=1&city=&page_size=100&strona=0"
OFFER_URL = f"{SITE}/pl/sprzedaz?menu=2&show={{id}}"

_FEATURE = re.compile(
    r'\{ "type": "Feature", "id":"(\d+)", "properties": \{ "address": "(.*?)"\}, '
    r'"geometry": \{ "type": "Point", "coordinates": \[([-\d.]+),([-\d.]+)\]'
)


@dataclass
class PkpItem:
    id: str
    city: str
    address: str
    lat: float
    lng: float
    photo_url: str | None
    category: str


def _field(html_text: str, label: str) -> str:
    m = re.search(rf"<b>\s*{label}:?\s*</b>\s*(.*?)(?:<br|$)", html_text)
    return m.group(1).strip() if m else ""


def parse_list(html: str) -> list[PkpItem]:
    items = []
    for fid, props, lng, lat in _FEATURE.findall(html):
        props = props.replace('\\"', '"').replace("\\/", "/")
        category = _field(props, "Kategoria")
        if "MIESZKAN" not in category.upper():
            continue
        m = re.search(r"<b>Adres:</b>\s*\d{2}-\d{3}\s+([^,<]+),<br\s*/>\s*([^<]+)", props)
        if not m:
            continue
        city = canonical_city(m.group(1))
        if city is None:
            continue
        img = re.search(r'<img src="([^"]+)"', props)
        items.append(PkpItem(
            id=fid,
            city=city,
            address=re.sub(r"\s*/\s*", "/", m.group(2).strip()),
            lat=float(lat),
            lng=float(lng),
            photo_url=SITE + quote(img.group(1)) if img else None,
            category=category,
        ))
    return items


def parse_offer(html: str, item: PkpItem) -> Offer | None:
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "nav", "header", "footer"]):
        t.decompose()
    text = " ".join(soup.get_text(" ").split())
    purpose = re.search(r"Przeznaczenie\s+(\S+)", text)
    ptype = "house" if purpose and fold(purpose.group(1)).startswith("dom") else (
        classify_type(text) or "flat"
    )
    area = re.search(r"Adres .*? Powierzchnia\s+(\d+(?:,\d+)?)\s*m\s*2", text)
    kind = re.search(r"Typ postępowania\s+(.*?)\s+Cena wywoławcza", text)
    price = re.search(r"Cena wywoławcza\s+([\d  .]+,\d{2})\s*zł", text)
    deposit = re.search(r"Wadium\s+([\d  .]+,\d{2})\s*zł", text)
    when = re.search(r"(?:Termin|Data)\s+(?:przetargu|postępowania)\s+(\S+)", text)
    kind_text = kind.group(1).lower() if kind else None
    return Offer(
        source=NAME,
        source_id=item.id,
        status="rokowania" if kind_text and "rokowan" in kind_text else "auction",
        type=ptype,
        city=item.city,
        address=item.address,
        area_m2=parse_area(area.group(1) + " m2") if area else None,
        start_price=parse_price(price.group(1)) if price else None,
        deposit=parse_price(deposit.group(1)) if deposit else None,
        auction_date=parse_date(when.group(1)) if when else None,
        auction_kind=kind_text,
        notice_url=OFFER_URL.format(id=item.id),
        photo_url=item.photo_url,
        raw_title=f"{item.city}, {item.address}",
        share=parse_share(text),
        lat=item.lat,
        lng=item.lng,
    )


def fetch(client: PoliteClient) -> list[Offer]:
    offers = []
    for item in parse_list(client.get(LIST_URL).text):
        offer = parse_offer(client.get(OFFER_URL.format(id=item.id)).text, item)
        if offer:
            offers.append(offer)
    return offers
