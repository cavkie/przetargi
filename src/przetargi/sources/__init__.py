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
    from . import gdansk

    return [Source(gdansk.NAME, gdansk.fetch)]


SOURCES: list[Source] = _registry()
