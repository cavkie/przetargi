"""Registry of the sources read on every run."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..http import PoliteClient
from ..models import Offer


@dataclass
class Source:
    name: str
    fetch: Callable[[PoliteClient], list[Offer]]
    expect_items: bool = True  # False: an empty result is normal (the source checks its own layout)


def _registry() -> list[Source]:
    from . import amw, gdansk, pkp, sopot

    return [Source(m.NAME, m.fetch) for m in (gdansk, sopot, pkp)] + [
        Source(amw.NAME, amw.fetch, expect_items=False)
    ]


SOURCES: list[Source] = _registry()
