"""Building positions from Nominatim (OpenStreetMap), cached forever."""
from __future__ import annotations

import re
from typing import Callable
from urllib.parse import quote

from .http import PoliteClient
from .models import Offer

Lookup = Callable[[str], "tuple[float, float] | None"]


def query_for(o: Offer) -> str:
    addr = re.sub(r"^\s*(ul|al|pl|os)\.\s*", "", o.address.strip(), flags=re.I)
    if re.search(r"\blok", addr, re.I):
        addr = re.split(r"\s*\blok", addr, maxsplit=1, flags=re.I)[0]
    else:
        addr = re.sub(r"/[\w,]+$", "", addr)  # "37/4" -> "37": the flat number confuses the search
    return f"{addr.strip(' ,')}, {o.city}, Polska"


def geocode_all(offers: dict[str, Offer], cache: dict[str, list[float] | None], lookup: Lookup) -> None:
    for o in offers.values():
        if o.lat is not None or not o.address.strip():
            continue
        q = query_for(o)
        if q not in cache:
            hit = lookup(q)
            cache[q] = [hit[0], hit[1]] if hit else None
        if cache[q]:
            o.lat, o.lng = cache[q]


def nominatim_lookup(client: PoliteClient) -> Lookup:
    def lookup(q: str) -> tuple[float, float] | None:
        r = client.get(
            "https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=pl&q="
            + quote(q),
            api=True,  # https://operations.osmfoundation.org/policies/nominatim/ allows 1 req/s
        )
        hits = r.json()
        return (float(hits[0]["lat"]), float(hits[0]["lon"])) if hits else None

    return lookup
