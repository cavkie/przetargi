"""Market comparison from RCN sale prices via the deweloperuch CLI (deweloperuch.pl)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from .models import Offer
from .places import AREA

UNAVAILABLE = "market data unavailable"


class Stopped(Exception):
    """The service refused (exit code 3): send nothing more this run, never lift it."""


def _executable() -> str:
    found = shutil.which("deweloperuch")
    if found:
        return found
    return str(Path(sys.executable).parent / "deweloperuch")


def run_cli(args: list[str]) -> dict:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    r = subprocess.run([_executable(), *args, "--json"], capture_output=True, env=env, timeout=180)
    stderr = r.stderr.decode("utf-8", errors="replace")
    if r.returncode == 3:
        raise Stopped(stderr.strip()[:300])
    if r.returncode != 0:
        raise RuntimeError(f"deweloperuch {' '.join(args)} exited {r.returncode}: {stderr[:300]}")
    return json.loads(r.stdout.decode("utf-8"))


def _months_before(today: str, n: int) -> str:
    y, m = int(today[:4]), int(today[5:7]) - n
    while m <= 0:
        y, m = y - 1, m + 12
    return f"{y:04d}-{m:02d}"


def city_median(transactions_json: dict, today: str) -> tuple[int, str] | None:
    periods = transactions_json.get("periods") or []
    wanted = transactions_json.get("last_complete_period")
    if wanted:
        candidates = [p for p in periods if p["period"] == wanted]
    else:
        cutoff = _months_before(today, 3)
        candidates = [p for p in periods if p["period"] <= cutoff and not p.get("incomplete")]
    candidates = [p for p in candidates if p.get("median_price_per_m2")]
    if not candidates:
        return None
    best = max(candidates, key=lambda p: p["period"])
    return round(best["median_price_per_m2"]), best["period"]


def _apply(o: Offer, result: dict) -> None:
    o.market_gap_pct = result["gap"]
    o.market_basis = result["basis"]
    o.market_low_confidence = result["low"]
    o.market_period = result["period"]


def apply_market(
    offers: dict[str, Offer],
    cache: dict[str, dict],
    cli: Callable[[list[str]], dict] = run_cli,
    today: str = "",
) -> str | None:
    medians: dict[str, tuple[int, str] | None] = {}
    for key, o in offers.items():
        if o.type != "flat" or not o.start_price:
            continue
        try:
            if o.lat is not None and o.lng is not None and o.area_m2 and 10 <= o.area_m2 <= 500:
                ck = f"{key}|{o.start_price}|{o.area_m2}"
                if ck not in cache:
                    v = cli(["valuation", "estimate", "--lat", str(o.lat), "--lng", str(o.lng),
                             "--area", str(o.area_m2), "--limit", "0"])
                    if v.get("estimated_value"):
                        cache[ck] = {
                            "gap": round((o.start_price / v["estimated_value"] - 1) * 100, 1),
                            "basis": "nearby",
                            "low": bool(v.get("low_confidence")),
                            "period": f"{v.get('period_months')} mies.",
                        }
                if ck in cache:
                    _apply(o, cache[ck])
                    continue
            slug = AREA.get(o.city)
            if not slug or not o.price_per_m2:
                continue
            if slug not in medians:
                medians[slug] = city_median(cli(["stats", "transactions", slug]), today)
            if medians[slug]:
                median, period = medians[slug]
                _apply(o, {"gap": round((o.price_per_m2 / median - 1) * 100, 1),
                           "basis": "city_median", "low": False, "period": period})
        except Stopped:
            return UNAVAILABLE
        except RuntimeError:
            continue  # one failed lookup leaves that row without a comparison
    return None
