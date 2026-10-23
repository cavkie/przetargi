"""UM Sopot BIP (Madkom): a JSON API behind the JavaScript site; details sit in .doc files."""
from __future__ import annotations

import html
import io
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

from ..http import PoliteClient
from ..models import Offer
from ..textutil import (
    classify_type,
    fold,
    is_cancellation,
    is_excluded_notice,
    parse_area,
    parse_date,
    parse_price,
)

NAME = "um-sopot"
BASE = "https://bip.sopot.pl/"
AUCTIONS_MENU = 107
WYKAZY_MENU = 117
PAGE = 50
MAX_ITEMS = 200


def classify_title(title: str) -> str:
    if is_cancellation(title):
        return "cancel" if classify_type(title) else "skip"
    if is_excluded_notice(title):
        return "skip"
    if re.search(r"sprzeda|zbyci|rokowan", fold(title)) and classify_type(title):
        return "sale"
    return "skip"


def parse_menu(json_text: str) -> list[tuple[int, str]]:
    data = json.loads(json_text)
    out = []
    for art in data.get("articles", []):
        title = next((f["value"] for f in art.get("aliasFields", []) if f.get("alias") == "title"), "")
        out.append((int(art["id"]), title.strip()))
    return out


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _html_text(fragment: str) -> str:
    return _flat(html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")))


def _address(text: str) -> str:
    t = _flat(text)
    street = re.search(
        r"przy\s+((?:ul\.|al\.|alei|al)\s*[^,;()]{1,50}?\s\d+[\w/-]*)(?:\s*\([^)]{0,30}\))?\s+w\s+Sopocie",
        t,
        re.I,
    )
    if not street:
        return ""
    addr = re.sub(r"^alei\s", "al. ", street.group(1).strip(), flags=re.I)
    lokal = re.search(r"lokal\w*\s+mieszkaln\w*\s+nr\s+([\w]+)", t, re.I)
    return f"{addr}/{lokal.group(1)}" if lokal else addr


def _kind(title: str) -> str | None:
    m = re.search(r"przetarg\w*\s+(ustn\w*|pisemn\w*)(\s+nieograniczon\w*|\s+ograniczon\w*)?", title, re.I)
    if m:
        return ("przetarg " + m.group(1) + (m.group(2) or "")).lower()
    return "rokowania" if "rokowan" in fold(title) else None


def _money_after(label: str, text: str) -> int | None:
    m = re.search(label + r".{0,200}?(\d[\d .]*,\d{2})\s*zł", text, re.I)
    return parse_price(m.group(1)) if m else None


def parse_article(article_json: str, attachment_text: str | None) -> Offer | None:
    art = json.loads(article_json)
    title = _flat(art.get("title") or "")
    kind = classify_title(title)
    if kind == "skip":
        return None
    body = _flat(attachment_text) if attachment_text else ""
    full = f"{title} {body or _html_text(art.get('content', ''))}"
    ptype = classify_type(title) or classify_type(full)
    if ptype is None:
        return None
    status = "cancelled" if kind == "cancel" else (
        "rokowania" if "rokowan" in fold(title) else "auction"
    )
    when = re.search(r"(?:Przetarg|Rokowania)\s+odb[eę]d\w*\s+si[eę].{0,80}", body, re.I)
    area = re.search(r"powierzchni\w*\s+u[zż]ytkow\w*\s+(?:lokalu\s+)?(?:wynosi\s+)?(\d+,\d+\s*m)", body, re.I)
    return Offer(
        source=NAME,
        source_id=str(art.get("id") or art.get("articleId")),
        status=status,
        type=ptype,
        city="Sopot",
        address=_address(title) or _address(full),
        area_m2=parse_area(area.group(1) + "²") if area else None,
        start_price=_money_after(r"Cena\s+wywo[lł]awcza", body) if body else None,
        deposit=_money_after(r"Wadium\s+w\s+wysoko[sś]ci", body) if body else None,
        auction_date=parse_date(when.group(0)) if when else None,
        auction_kind=_kind(title),
        notice_url=BASE + art["link"],
        photo_url=None,
        raw_title=title,
    )


_WYKAZ_SKIP = re.compile(r"dzierzaw|najem|najmu|uzyczen|uzytkow|garaz|niemieszkal|gruntow\w* niezabud")


def parse_wykaz_attachments(article_json: str) -> list[tuple[int, str]]:
    """Attachments of a half-year wykazy article that may describe a flat or house for sale."""
    art = json.loads(article_json)
    out = []
    for att in art.get("attachments", []):
        name = _flat(att.get("name") or "")
        n = fold(name)
        if att.get("deleted") or _WYKAZ_SKIP.search(n):
            continue
        if "lokal" in n or "zabudowan" in n or classify_type(name):
            out.append((int(att["id"]), name))
    return out


def wykaz_offer(attachment_id: int, name: str, text: str) -> Offer | None:
    body = _flat(text)
    ptype = classify_type(body)
    if ptype is None:  # leases are already excluded by the attachment name
        return None
    return Offer(
        source=NAME,
        source_id=f"wykaz-{attachment_id}",
        status="planned",
        type=ptype,
        city="Sopot",
        address=_address(body) or _address(name),
        area_m2=None,
        start_price=None,
        deposit=None,
        auction_date=None,
        auction_kind=None,
        notice_url=f"{BASE}e,pobierz,get.html?id={attachment_id}",
        photo_url=None,
        raw_title=name,
    )


def doc_to_text(data: bytes) -> str | None:
    if data[:2] == b"PK":  # .docx
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                xml = z.read("word/document.xml").decode("utf-8")
        except (zipfile.BadZipFile, KeyError):
            return None
        xml = re.sub(r"</w:p>", "\n", xml)
        return html.unescape(re.sub(r"<[^>]+>", "", xml))
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "a.doc"
        path.write_bytes(data)
        try:
            r = subprocess.run(
                ["antiword", "-m", "UTF-8.txt", str(path)], capture_output=True, timeout=60
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
    text = r.stdout.decode("utf-8", errors="replace")
    return text if r.returncode == 0 and text.strip() else None


def _attachment_text(client: PoliteClient, art: dict) -> str | None:
    for att in art.get("attachments", []):
        if att.get("extension") in ("doc", "docx") and "rzut" not in fold(att.get("name") or ""):
            return doc_to_text(client.get_bytes(BASE + att["link"]))
    return None


def fetch(client: PoliteClient) -> list[Offer]:
    offers: list[Offer] = []
    for offset in range(0, MAX_ITEMS, PAGE):
        items = parse_menu(
            client.get(f"{BASE}api/menu/{AUCTIONS_MENU}/articles?limit={PAGE}&offset={offset}").text
        )
        if not items:
            break
        for art_id, title in items:
            if classify_title(title) == "skip":
                continue
            raw = client.get(f"{BASE}api/articles/{art_id}").text
            offer = parse_article(raw, _attachment_text(client, json.loads(raw)))
            if offer:
                offers.append(offer)
    wykazy = parse_menu(client.get(f"{BASE}api/menu/{WYKAZY_MENU}/articles?limit=1&offset=0").text)
    for art_id, _ in wykazy[:1]:  # the current half-year or year
        raw = client.get(f"{BASE}api/articles/{art_id}").text
        for att_id, name in parse_wykaz_attachments(raw):
            text = doc_to_text(client.get_bytes(f"{BASE}e,pobierz,get.html?id={att_id}"))
            offer = wykaz_offer(att_id, name, text) if text else None
            if offer:
                offers.append(offer)
    return offers
