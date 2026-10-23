"""UM Gdańsk, Wydział Skarbu: one article per auction day, each with a PDF of tables."""
from __future__ import annotations

import io
import re
from pathlib import PurePosixPath
from urllib.parse import urljoin, urlsplit

import pdfplumber
from bs4 import BeautifulSoup

from ..http import PoliteClient
from ..models import Offer
from ..textutil import classify_type, fold, parse_area, parse_date, parse_price

NAME = "um-gdansk"
LIST_URL = "https://gdansk.pl/urzad-miejski/ogloszenia-o-przetargach,a,1439"

_FLOOR = re.compile(r"pi[eę]tro|parter|poddasze|kondygnac|suteren|mpzp", re.I)


def parse_list(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        url = urljoin(base_url, a["href"])
        if "/urzad-miejski/ogloszenie-o-przetarg" in url and ",a," in url and url not in out:
            out.append(url)
    return out


def parse_article(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        url = urljoin(base_url, a["href"])
        if url.lower().endswith(".pdf") and "cloudgdansk" in url and url not in out:
            out.append(url)
    return out


def _lines(cell: str | None) -> list[str]:
    return [ln.strip() for ln in (cell or "").splitlines() if ln.strip()]


def _address(location: str | None) -> str:
    lines = _lines(location)[1:]  # first line is "Gdańsk – <district>"
    parts: list[str] = []
    for ln in lines:
        if _FLOOR.search(ln):
            break
        parts.append(ln)
    return " ".join(parts)


def _is_lokal_table(header: list[str | None]) -> bool:
    return any("lokalu" in fold(h or "") for h in header)


def parse_auction_pdf(pdf_bytes: bytes, notice_url: str) -> list[Offer]:
    offers: list[Offer] = []
    stem = PurePosixPath(urlsplit(notice_url).path).stem
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        first_text = pdf.pages[0].extract_text() or ""
        auction_date = parse_date(first_text)
        for page in pdf.pages:
            for table in page.extract_tables():
                if not table or not table[0]:
                    continue
                lokal = _is_lokal_table(table[0])
                rows = table[2:]  # two header rows
                for i, row in enumerate(rows):
                    if not row or not re.fullmatch(r"\d+\.", (row[0] or "").strip()):
                        continue
                    nxt = rows[i + 1] if i + 1 < len(rows) else [None] * len(row)
                    offer = _row_to_offer(row, nxt, lokal, auction_date, notice_url, stem)
                    if offer:
                        offers.append(offer)
    return offers


def _row_to_offer(row, nxt, lokal, auction_date, notice_url, stem) -> Offer | None:
    text = " ".join(c or "" for c in row)
    if lokal:
        # lokal tables describe flats as "Lokal obejmujący 2 pokoje..."
        ptype = None if re.search(r"lokal\w* uzytkow", fold(text)) else "flat"
    else:
        # skip the location cell: its MPZP zoning text mentions "zabudowa mieszkaniowa"
        ptype = classify_type(" ".join(c or "" for c in row[2:]))
    if ptype is None:
        return None
    if lokal:
        area = parse_area(row[3])
        price_cell, deposit_cell, kind_col = row[4], row[5], 6
    else:
        area = None
        price_cell, deposit_cell, kind_col = row[3], row[4], 5
    kind_cell = nxt[kind_col] if kind_col < len(nxt) else None
    kind = " ".join(ln for ln in _lines(kind_cell) if not ln.startswith("godz")) or None
    loc = _lines(row[1])
    return Offer(
        source=NAME,
        source_id=f"{stem}#{(row[0] or '').strip(' .')}",
        status="auction",
        type=ptype,
        city="Gdańsk",
        address=_address(row[1]),
        area_m2=area,
        start_price=parse_price(_lines(price_cell)[0] if _lines(price_cell) else None),
        deposit=parse_price(_lines(deposit_cell)[0] if _lines(deposit_cell) else None),
        auction_date=auction_date,
        auction_kind=kind,
        notice_url=notice_url,
        photo_url=None,
        raw_title=loc[0] if loc else "",
    )


def fetch(client: PoliteClient) -> list[Offer]:
    offers: list[Offer] = []
    for article in parse_list(client.get(LIST_URL).text, LIST_URL):
        for pdf_url in parse_article(client.get(article).text, article):
            offers.extend(parse_auction_pdf(client.get_bytes(pdf_url), pdf_url))
    return offers
