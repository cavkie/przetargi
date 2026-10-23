"""Records shared by every source, the archive and the page."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

Status = Literal["planned", "auction", "rokowania", "cancelled"]
PropType = Literal["flat", "house"]


@dataclass
class Round:
    date: str
    status: Status
    start_price: int | None
    auction_date: str | None
    notice_url: str


@dataclass
class Offer:
    source: str
    source_id: str
    status: Status
    type: PropType
    city: str
    address: str
    area_m2: float | None
    start_price: int | None
    deposit: int | None
    auction_date: str | None
    auction_kind: str | None
    notice_url: str
    photo_url: str | None
    raw_title: str
    first_seen: str | None = None
    last_seen: str | None = None
    price_history: list[Round] = field(default_factory=list)
    price_drop: bool = False
    lat: float | None = None
    lng: float | None = None
    market_gap_pct: float | None = None
    market_basis: Literal["nearby", "city_median"] | None = None
    market_low_confidence: bool = False
    market_period: str | None = None

    @property
    def price_per_m2(self) -> int | None:
        if not self.start_price or not self.area_m2:
            return None
        return round(self.start_price / self.area_m2)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Offer:
        d = dict(d)
        d["price_history"] = [Round(**r) for r in d.get("price_history", [])]
        return cls(**d)


@dataclass
class SourceStatus:
    source: str
    ok: bool
    count: int
    at: str
    error: str | None = None
    warning: str | None = None
