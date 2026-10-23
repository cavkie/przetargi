"""Build the static page: one table, data embedded as JSON, CSS and JS inlined."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader

from .archive import is_archived
from .models import Offer, SourceStatus

HERE = Path(__file__).parent
FOOTER = "Szacunek, nie operat. Dane rynkowe: deweloperuch.pl (RCN). To nie jest porada finansowa."
MANUAL_LINKS = [
    ("Licytacje komornicze", "https://licytacje.komornik.pl", "Pomorskie → Gdańsk / Sopot, nieruchomości"),
    ("Licytacje urzędów skarbowych", "https://elicytacje.mf.gov.pl", "eLicytacje KAS"),
    ("Obwieszczenia syndyków", "https://krz.ms.gov.pl", "KRZ, sprawy GD1G/GUp/…"),
    ("Oferty syndyków na portalach", "https://tabelaofert.pl", "np. tabelaofert.pl"),
    ("Wykazy nieruchomości Gdańska", "https://baw.bip.gdansk.pl/UrzadMiejskiwGdansku/tabBrowser/mainPage",
     "zarządzenia Prezydenta – załączniki z wykazami"),
]
SOURCE_LABELS = {"um-gdansk": "UM Gdańsk", "um-sopot": "UM Sopot", "pkp": "PKP", "amw": "AMW"}


def maps_url(o: Offer) -> str:
    return "https://www.google.com/maps/search/?api=1&query=" + quote(f"{o.address}, {o.city}", safe="")


def streetview_url(o: Offer) -> str | None:
    if o.lat is None or o.lng is None:
        return None
    return f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={o.lat},{o.lng}"


def _row(o: Offer, today: str) -> dict:
    d = asdict(o)
    d.update(
        maps=maps_url(o),
        streetview=streetview_url(o),
        new=o.first_seen == today,
        archived=is_archived(o, today),
        price_per_m2=o.price_per_m2,
        source_label=SOURCE_LABELS.get(o.source, o.source),
    )
    return d


def _json_for_script(data) -> str:
    # keep "</script>" and friends from closing the data block
    return (json.dumps(data, ensure_ascii=False)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def render_site(offers: dict[str, Offer], statuses: list[SourceStatus], today: str, site_dir: Path) -> None:
    rows = sorted((_row(o, today) for o in offers.values()),
                  key=lambda r: (r["auction_date"] or "9999", r["city"], r["address"]))
    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=True)
    html = env.get_template("index.html.j2").render(
        today=today,
        statuses=statuses,
        source_labels=SOURCE_LABELS,
        updated=max((s.at for s in statuses), default=today),
        active=sum(1 for r in rows if not r["archived"]),
        new=sum(1 for r in rows if r["new"] and not r["archived"]),
        manual_links=MANUAL_LINKS,
        footer=FOOTER,
        css=(HERE / "static" / "app.css").read_text(encoding="utf-8"),
        js=(HERE / "static" / "app.js").read_text(encoding="utf-8"),
        data=_json_for_script({"today": today, "offers": rows}),
    )
    site_dir = Path(site_dir)
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "index.html").write_text(html, encoding="utf-8")
