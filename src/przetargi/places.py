"""The monitored area and city-name canonicalisation."""
from __future__ import annotations

from .textutil import fold

# canonical city -> deweloperuch city slug
AREA: dict[str, str] = {
    "Gdańsk": "gdansk",
    "Sopot": "sopot",
    "Gdynia": "gdynia",
    "Pruszcz Gdański": "pruszcz-gdanski",
    "Kolbudy": "kolbudy",
    "Żukowo": "zukowo",
    "Rumia": "rumia",
}

_BY_FOLDED = {fold(name): name for name in AREA}


def canonical_city(s: str | None) -> str | None:
    if not s:
        return None
    return _BY_FOLDED.get(fold(s).strip())
