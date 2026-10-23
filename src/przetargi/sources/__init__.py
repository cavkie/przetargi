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


def _registry() -> list[Source]:
    from . import amw, gdansk, pkp, sopot

    return [Source(m.NAME, m.fetch) for m in (gdansk, sopot, pkp, amw)]


SOURCES: list[Source] = _registry()
