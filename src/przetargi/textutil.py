"""Parsing of Polish prices, areas, dates, addresses and notice titles."""
from __future__ import annotations

import re
import unicodedata

from .models import PropType

MONTHS = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5, "czerwca": 6,
    "lipca": 7, "sierpnia": 8, "września": 9, "października": 10, "listopada": 11,
    "grudnia": 12,
}


def fold(s: str) -> str:
    """Lowercase and strip Polish diacritics (ł has no decomposition)."""
    s = s.replace("ł", "l").replace("Ł", "L")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _to_number(raw: str) -> float | None:
    raw = raw.replace(" ", " ").replace(" ", " ").strip()
    raw = re.sub(r"(?<=\d) (?=\d{3}\b)", "", raw)
    if "," in raw:
        # Polish decimal comma; dots are thousand separators
        raw = raw.replace(".", "").replace(" ", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", raw):
        raw = raw.replace(".", "")
    raw = raw.replace(" ", "")
    try:
        return float(raw)
    except ValueError:
        return None


_NUM = r"\d[\d   .]*(?:,\d+)?"


def parse_price(s: str | None) -> int | None:
    if not s:
        return None
    m = re.search(_NUM, s)
    if not m:
        return None
    value = _to_number(m.group(0))
    return round(value) if value is not None else None


def parse_area(s: str | None) -> float | None:
    if not s:
        return None
    # "1 048,37" / "1.144" use thousand separators; "48.5" is a decimal point
    m = re.search(
        r"(?<![\d,.])(\d{1,3}(?:[   .]\d{3})+(?:,\d+)?|\d+(?:[,.]\d+)?)\s*m\s*(?:²|2|\^2|kw)",
        s,
    )
    if not m:
        return None
    return _to_number(m.group(1))


def parse_date(s: str | None) -> str | None:
    if not s:
        return None
    m = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", s)
    if m:
        d, mo, y = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"
    m = re.search(r"\b(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{4})", s.lower())
    if m and m.group(2) in MONTHS:
        return f"{int(m.group(3)):04d}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}"
    return None


def normalise_address(s: str) -> str:
    s = fold(s)
    s = re.sub(r"^\s*(ul|al|pl|os)\.\s*", "", s)
    s = re.sub(r"\s*(?:lok\.|lokal(?:u)?(?:\s+nr)?|m\.|nr\s+lok\.?)\s*", "/", s)
    s = re.sub(r"\s*/\s*", "/", s)
    s = re.sub(r"/+", "/", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" ,/")


def classify_type(text: str) -> PropType | None:
    t = fold(text)
    # a flat is often sold "in a plot built with a residential building", so flats win
    if re.search(r"lokal\w* mieszkaln|prawo do lokalu|\bmieszkanie\b", t):
        return "flat"
    if re.search(r"zabudowan\w* budynk\w* mieszkaln|dom\w* jednorodzin|\bdom\b|domu mieszkaln", t):
        if "niezabudowan" not in t:
            return "house"
    return None


def is_excluded_notice(title: str) -> bool:
    t = fold(title)
    return bool(
        re.search(
            r"\bnajem|\bnajmu|dzierzaw|rozstrzygniet|zakonczon|uniewazni"
            r"|informacj\w* o wynik|wynik\w* (?:\w+ )?(?:przetarg|rokowan)",
            t,
        )
    )


def is_cancellation(title: str) -> bool:
    return bool(re.search(r"odwolani|odwoluj", fold(title)))
