"""Agencja Mienia Wojskowego: tenders list for Pomorskie, details per tender page."""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..http import PoliteClient
from ..models import Offer
from ..places import canonical_city
from ..textutil import classify_type, fold, parse_area, parse_date, parse_price

NAME = "amw"
BASE = "https://amw.com.pl/pl/nieruchomosci/przetargi-nieruchomosci"
LIST_URL = f"{BASE}/wyniki-wyszukiwania/page,0,limit,200,zone,82"


def parse_list(html: str, base_url: str) -> list[tuple[str, str]]:
    """(detail url, canonical city) of sales in the monitored area."""
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select("div.element")
    if not rows:  # Pomorskie always has some AMW tenders; none means the layout changed
        raise ValueError("AMW list has no result rows")
    out = []
    for el in rows:
        link = el.select_one("h2 a[href]")
        if not link:
            continue
        info = " ".join(el.get_text(" ").split())
        if "Sprzedaż" not in info:
            continue
        city = canonical_city(link.get_text(strip=True))
        if city:
            out.append((urljoin(base_url, link["href"]), city))
    return out


def parse_detail(html: str, url: str, city: str) -> Offer | None:
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "nav", "header", "footer"]):
        t.decompose()
    text = " ".join(soup.get_text(" ").split())
    if not re.search(r"Ogłoszenie o przetargu\s*-\s*Sprzedaż", text):
        return None
    category = re.search(r"Kategoria\s+(.*?)\s+Ogłoszenie", text)
    title = soup.find(["h1", "title"])
    title_text = " ".join(title.get_text(" ").split()) if title else ""
    ptype = classify_type(f"{category.group(1) if category else ''} {title_text}")
    if ptype is None:
        return None
    address = re.sub(rf"^{re.escape(city)}\s*,?\s*", "", title_text.split(" - ")[0]).strip()
    area = re.search(r"użytkowa:\s*(\d+(?:,\d+)?)\s*m\s*2", text)
    price = re.search(r"Cena wywoławcza\s+([\d  .]+,\d{2})\s*PLN", text)
    when = re.search(r"Przetarg w dniu:\s*(\d{2}\.\d{2}\.\d{4})", text)
    img = next((i["src"] for i in soup.find_all("img", src=True)
                if "images_cache/amw_estate_image" in i["src"] and "no_photo" not in i["src"]), None)
    sid = re.search(r"-(\d+)/?$", url)
    return Offer(
        source=NAME,
        source_id=sid.group(1) if sid else url,
        status="rokowania" if "rokowan" in fold(text) else "auction",
        type=ptype,
        city=city,
        address=address,
        area_m2=parse_area(area.group(1) + " m2") if area else None,
        start_price=parse_price(price.group(1)) if price else None,
        deposit=None,
        auction_date=parse_date(when.group(1)) if when else None,
        auction_kind=None,
        notice_url=url,
        photo_url=img,
        raw_title=title_text,
    )


def fetch(client: PoliteClient) -> list[Offer]:
    offers = []
    for url, city in parse_list(client.get(LIST_URL).text, BASE):
        offer = parse_detail(client.get(url).text, url, city)
        if offer:
            offers.append(offer)
    return offers
