"""The permanent archive: one row per property, merged on every run."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from .models import Offer, Round
from .textutil import normalise_address

ARCHIVE_AFTER_DAYS = 14
_MERGEABLE = (
    "source_id", "type", "city", "address", "area_m2", "start_price", "deposit",
    "auction_date", "auction_kind", "notice_url", "photo_url", "raw_title",
)


def offer_key(o: Offer) -> str:
    addr = normalise_address(o.address) if o.address else ""
    return f"{o.source}|{addr or o.source_id}"


def _round(o: Offer, run_date: str) -> Round:
    return Round(date=run_date, status=o.status, start_price=o.start_price,
                 auction_date=o.auction_date, notice_url=o.notice_url)


def _merge_one(old: Offer, new: Offer, run_date: str) -> None:
    old.last_seen = run_date
    if new.status == "planned" and old.status in ("auction", "rokowania"):
        return  # a wykaz never overwrites a real auction
    if new.status == "cancelled":
        old.status = "cancelled"
        old.notice_url = new.notice_url or old.notice_url
        return
    old.status = new.status
    for f in _MERGEABLE:
        value = getattr(new, f)
        if value is not None and value != "":
            setattr(old, f, value)
    last = old.price_history[-1] if old.price_history else None
    if last is None or (last.start_price, last.status, last.auction_date) != (
        old.start_price, old.status, old.auction_date
    ):
        old.price_history.append(_round(old, run_date))
    prices = [r.start_price for r in old.price_history if r.start_price is not None]
    old.price_drop = len(prices) >= 2 and prices[-1] < prices[-2]


def merge(existing: dict[str, Offer], fetched: list[Offer], run_date: str) -> dict[str, Offer]:
    out = dict(existing)
    for o in fetched:
        k = offer_key(o)
        if k in out:
            _merge_one(out[k], o, run_date)
        else:
            o.first_seen = o.last_seen = run_date
            o.price_history = [_round(o, run_date)]
            out[k] = o
    return out


def is_archived(o: Offer, today: str) -> bool:
    if o.status == "cancelled":
        return True
    if o.auction_date and o.auction_date < today:
        return True
    if o.last_seen:
        cutoff = date.fromisoformat(today) - timedelta(days=ARCHIVE_AFTER_DAYS)
        if date.fromisoformat(o.last_seen) < cutoff:
            return True
    return False


def load(path: Path) -> dict[str, Offer]:
    path = Path(path)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k: Offer.from_dict(v) for k, v in raw.items()}


def save(path: Path, offers: dict[str, Offer]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {k: offers[k].to_dict() for k in sorted(offers)}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
