# Przetargi Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A daily GitHub Actions job collects flat and house sale notices (auctions, rokowania, planned wykazy) for Gdańsk, Sopot and nearby towns, compares flats with market sale prices, keeps a JSON archive in git, and publishes one sortable table on GitHub Pages.

**Architecture:** There is one Python package, `przetargi`.
- **Sources:** each source is a module with a network `fetch()` and a pure `parse_*()` that turns saved HTML, JSON or text into `Offer` records.
- **Pipeline:** `run.py` fetches every source, isolating each one's failures, then merges the results into `data/offers.json` (one row per property). Next it adds coordinates (Nominatim) and market estimates (the deweloperuch CLI), both cached. Finally it renders a static `site/index.html`, with the data embedded and a little plain JavaScript for sorting, filters and tabs.

**Tech Stack:**
- Python 3.11+ managed with uv
- httpx, beautifulsoup4 + lxml, pdfplumber, jinja2
- pytest for tests
- antiword on the Ubuntu runner, to read Sopot's .doc attachments
- deweloperuch-mcp (the CLI)
- GitHub Actions + Pages

**Spec:** `docs/superpowers/specs/2026-10-23-przetargi-monitor-design.md`

## Global Constraints

- **Area:** Gdańsk, Sopot, Gdynia, Pruszcz Gdański (town and gmina), Kolbudy, Żukowo and Rumia. Nearby towns come only from PKP and AMW.
- **Property types:** only flats (lokal mieszkalny, spółdzielcze własnościowe prawo do lokalu) and houses (nieruchomość zabudowana budynkiem mieszkalnym / dom). Exclude rentals (najem/dzierżawa), garages, commercial premises and land.
- **Statuses:** `planned` (wykaz), `auction`, `rokowania`, `cancelled`.
- **No made-up values:** a field that can't be parsed stays `None` and renders as "—".
- **Politeness:**
  - User-Agent `przetargi-monitor/1.0 (+https://github.com/cavkie/przetargi)`.
  - At least 1 s between requests to the same host.
  - Respect robots.txt. AMW: never fetch `/uploads/*.pdf`.
  - Nominatim: 1 request/s, results cached permanently.
  - deweloperuch: commands run one at a time. After exit code 3 (STOP), make no more calls in that run. Never lift a STOP.
- **Failure visibility:** one failing source must not stop the others. Each source's status (ok/failed, error text, count, time) is shown on the page.
- **Schedule:** cron `0 4 * * *` (UTC) plus `workflow_dispatch`.
- **Repository:** public repo `cavkie/przetargi`. Pages source is GitHub Actions.
- **Footer copy (exact):** "Szacunek, nie operat. Dane rynkowe: deweloperuch.pl (RCN). To nie jest porada finansowa."
- **Check-by-hand links (exact URLs):**
  - https://licytacje.komornik.pl
  - https://elicytacje.mf.gov.pl
  - https://krz.ms.gov.pl
  - https://tabelaofert.pl

## Review Focus

1. **One Gdańsk PDF can hold several properties, including non-residential ones** (land, a shop) in the same table. Expected: one row per flat or house, and the others are dropped. *Test:* `test_gdansk_pdf_keeps_only_residential` (Task 3).
2. **The same flat at a second auction with a lower price, in a new notice.** Expected: one row, with a price history of 2 entries, `price_drop=True`, and *not* marked new. *Test:* `test_merge_second_round_lower_price` (Task 2).
3. **A source fails or returns zero items because its HTML changed.** Expected: the status is `failed`, or `ok` with count 0 and a warning. The archive rows from that source stay untouched. *Tests:* `test_run_isolates_failing_source` and `test_zero_items_is_warning` (Task 8).
4. **Polish formats:** prices like `1 250 000,00 zł` (spaces, including non-breaking spaces), areas like `48,37 m²`, and dates like `26 października 2026 r.` / `26.10.2026`. Expected: parsed correctly, never off by a factor of 100. *Test:* `test_parse_numbers_and_dates` (Task 1).
5. **A Sopot or Gdańsk item that is a rental or a finished tender** ("najem", "ROZSTRZYGNIĘTY", "ZAKOŃCZONY", "informacja o wyniku"). Expected: excluded. A cancellation ("odwołanie") turns the matching row into `cancelled`. *Tests:* `test_sopot_classify_titles` (Task 4) and `test_merge_cancellation` (Task 2).

---

## File Structure

```
przetargi/
  pyproject.toml
  .github/workflows/daily.yml
  src/przetargi/
    models.py        Offer, Round, SourceStatus dataclasses + JSON (de)serialisation
    textutil.py      parse_price, parse_area, parse_date, normalise_address, classify_type
    places.py        AREA list, city canonicalisation, in_area(), deweloperuch city slugs
    http.py          PoliteClient (UA, per-host delay, robots.txt)
    archive.py       load/save, offer_key(), merge(), is_archived()
    sources/
      __init__.py    SOURCES registry: list[Source]
      gdansk.py      auctions list + PDFs, wykazy pages
      sopot.py       BIP JSON API menu 107 (auctions) + 117 (wykazy), .doc via antiword
      pkp.py         pkp.pl/pl/sprzedaz listing + offer pages
      amw.py         amw.com.pl przetargi-nieruchomosci listing
    geocode.py       Nominatim with permanent cache
    market.py        deweloperuch CLI wrapper, cache, STOP handling
    render.py        build site/index.html from offers + statuses
    templates/index.html.j2
    static/app.js, static/app.css
    run.py           orchestrator: python -m przetargi.run
  data/              offers.json, status.json, geocode.json, market.json (committed by CI)
  tests/
    fixtures/<source>/...
    test_*.py
```

---

### Task 1: Project scaffold, models, text utilities, places

**Files:**
- Create:
  - `pyproject.toml`
  - `.gitignore` (`site/`, `.venv/`, `__pycache__/`, `.superpowers/`)
  - `src/przetargi/__init__.py`
  - `src/przetargi/models.py`
  - `src/przetargi/textutil.py`
  - `src/przetargi/places.py`
- Test:
  - `tests/test_textutil.py`
  - `tests/test_places.py`

**Interfaces:**
- **Produces, `models.py`:**
  - `Status = Literal["planned","auction","rokowania","cancelled"]`
  - `PropType = Literal["flat","house"]`
  - `@dataclass Round(date: str, status: Status, start_price: int|None, auction_date: str|None, notice_url: str)`
  - `@dataclass Offer`:
    - Identity and status: `source: str` (one of `"um-gdansk","um-sopot","pkp","amw"`), `source_id: str`, `status: Status`, `type: PropType`
    - Location: `city: str` (canonical, e.g. "Gdańsk"), `address: str`
    - Prices and sale terms (`int|None` = whole zł): `area_m2: float|None`, `start_price: int|None`, `deposit: int|None`, `auction_date: str|None` (ISO), `auction_kind: str|None`
    - Links and raw text: `notice_url: str`, `photo_url: str|None`, `raw_title: str`
    - Archive bookkeeping, set by merge: `first_seen: str|None = None`, `last_seen: str|None = None`, `price_history: list[Round] = []`, `price_drop: bool = False`
    - Coordinates: `lat: float|None = None`, `lng: float|None = None`
    - Market: `market_gap_pct: float|None = None`, `market_basis: Literal["nearby","city_median"]|None = None`, `market_low_confidence: bool = False`, `market_period: str|None = None`
    - Derived: property `price_per_m2 -> int|None`
  - `Offer.to_dict() / Offer.from_dict(d)`
  - `@dataclass SourceStatus(source: str, ok: bool, count: int, at: str, error: str|None = None, warning: str|None = None)`
- **Produces, `textutil.py`:**
  - `parse_price(s) -> int|None`
  - `parse_area(s) -> float|None`
  - `parse_date(s) -> str|None` (ISO)
  - `normalise_address(s) -> str`
  - `classify_type(text) -> PropType|None` (None means not residential)
  - `is_excluded_notice(title) -> bool` (rental or finished)
  - `is_cancellation(title) -> bool`
- **Produces, `places.py`:**
  - `AREA: dict[str, str]`: canonical city → deweloperuch slug (`"Gdańsk":"gdansk"`, `"Sopot":"sopot"`, `"Gdynia":"gdynia"`, `"Pruszcz Gdański":"pruszcz-gdanski"`, `"Kolbudy":…`, `"Żukowo":…`, `"Rumia":"rumia"`)
  - `canonical_city(s) -> str|None` (folds case and diacritics, returns None outside AREA)

- [ ] **Step 1: Init the repo.** Run `git init` in `E:\mieszkania\przetargi`. Create `pyproject.toml`:
  - Package `przetargi`, src layout, `requires-python = ">=3.11"`.
  - Dependencies: `httpx`, `beautifulsoup4`, `lxml`, `pdfplumber`, `jinja2`, `deweloperuch-mcp`.
  - Dev group: `pytest`.
  - Run `uv sync`. Expected: it resolves without errors.
- [ ] **Step 2: Write the failing tests.**

```python
# tests/test_textutil.py
def test_parse_numbers_and_dates():
    assert parse_price("1 250 000,00 zł") == 1250000
    assert parse_price("1\u00a0250\u00a0000 zł") == 1250000
    assert parse_price("500.000,00 zł") == 500000
    assert parse_price("brak") is None
    assert parse_area("48,37 m²") == 48.37
    assert parse_area("pow. użytkowa 61,2 m2") == 61.2
    assert parse_date("26 października 2026 r.") == "2026-10-26"
    assert parse_date("26.10.2026") == "2026-10-26"
    assert parse_date("dnia 3 listopada 2026") == "2026-11-03"

def test_normalise_address():
    assert normalise_address("ul. Uczniowska 37/4") == normalise_address("Uczniowska 37 lok. 4")
    assert normalise_address("ul. Góreckiego 8/3,4A") == "goreckiego 8/3,4a"
    assert normalise_address("Armii Krajowej 61 lokal nr 1") == "armii krajowej 61/1"

def test_classify_type():
    assert classify_type("sprzedaż lokalu mieszkalnego nr 4") == "flat"
    assert classify_type("spółdzielcze własnościowe prawo do lokalu") == "flat"
    assert classify_type("nieruchomość zabudowana budynkiem mieszkalnym jednorodzinnym") == "house"
    assert classify_type("lokal użytkowy") is None
    assert classify_type("nieruchomość niezabudowana") is None
    assert classify_type("garaż") is None

def test_notice_flags():
    assert is_excluded_notice("Przetarg na najem lokalu użytkowego")
    assert is_excluded_notice("PRZETARG ROZSTRZYGNIĘTY - lokal mieszkalny")
    assert is_excluded_notice("Informacja o wyniku przetargu")
    assert is_cancellation("Odwołanie przetargu na sprzedaż lokalu mieszkalnego")
    assert not is_excluded_notice("II publiczny przetarg ustny nieograniczony na sprzedaż lokalu mieszkalnego")

# tests/test_places.py
def test_canonical_city():
    assert canonical_city("GDANSK") == "Gdańsk"
    assert canonical_city("Pruszcz Gdański") == "Pruszcz Gdański"
    assert canonical_city("Słupsk") is None
```

- [ ] **Step 3: Run the tests to check they fail.** Run `uv run pytest -q`. Expected: FAIL, because of import errors.
- [ ] **Step 4: Implement `models.py`, `textutil.py` and `places.py` against the interfaces above.**
  - Month names: all 12 Polish genitive forms.
  - `normalise_address`:
    - fold diacritics, lowercase
    - drop the `ul.`/`al.`/`pl.` prefixes
    - turn `lok.`/`lokal nr`/`m.` into `/`
    - collapse whitespace
  - Before finishing the slugs, run `uvx --from deweloperuch-mcp deweloperuch locations search <name> --json` once for each of Kolbudy and Żukowo, and hardcode the `city_slug` it returns. If there is no city entry, use `None`; that town then simply gets no city-median comparison.
- [ ] **Step 5: Run the tests to check they pass.** Run `uv run pytest -q`. Expected: all pass.
- [ ] **Step 6: Commit.** Message: `feat: models, text utils, area list`.

### Task 2: Archive merge

**Files:**
- Create: `src/przetargi/archive.py`
- Test: `tests/test_archive.py`

**Interfaces:**
- **Consumes:** `Offer`, `Round`, `normalise_address` (Task 1).
- **Produces:**
  - `offer_key(o: Offer) -> str`: `f"{o.source}|{normalise_address(o.address)}"`. PKP and AMW use `f"{source}|{source_id}"` when the address is empty.
  - `merge(existing: dict[str, Offer], fetched: list[Offer], run_date: str) -> dict[str, Offer]`
  - `is_archived(o: Offer, today: str) -> bool`
  - `load(path) -> dict[str, Offer]`, `save(path, offers)`. Saves as sorted, pretty JSON so git diffs stay readable.

**Merge rules (from the spec):**
- **New key:** set `first_seen = last_seen = run_date` and add one `Round`.
- **Existing key:** set `last_seen = run_date`. Fields that are not `None` in the fetched offer overwrite the stored ones.
- **Status precedence:**
  - `cancelled` from a fetch always wins.
  - `planned` never overwrites `auction` or `rokowania`.
  - `auction`/`rokowania` overwrite `planned`.
- **Price rounds:** append a `Round` when `start_price`, `status` or `auction_date` changes. Set `price_drop = True` when the newest round's price is below the previous non-None price.
- **Unfetched keys** are left unchanged. Merge is called per successful source with only that source's offers.

**`is_archived(o, today)`** is true when any of these holds:
- `status == "cancelled"`
- `auction_date` is set and earlier than `today`
- `last_seen` is more than 14 days before `today`

- [ ] **Step 1: Write the failing tests.**
  - `test_merge_new_offer`: `first_seen` equals the run date, and there is 1 round.
  - `test_merge_second_round_lower_price`: a stored auction at 500000; then a fetch of the same address as `rokowania` at 400000. Expect 1 key, 2 rounds, `price_drop is True`, and `first_seen` unchanged (so it is not new).
  - `test_merge_planned_then_auction`: a planned row with no price, then an auction with 300000 → one row with status `auction`.
  - `test_merge_auction_not_downgraded_by_wykaz`.
  - `test_merge_cancellation`: an auction, then a fetched `cancelled` → status `cancelled`, and `is_archived` is true.
  - `test_is_archived_rules`: covers a past date, `last_seen` 15 days ago vs 13 days ago, and a future date.
  - `test_save_load_roundtrip`.
- [ ] **Step 2: Run** `uv run pytest tests/test_archive.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement `archive.py` by the rules above.**
- [ ] **Step 4: Run** `uv run pytest tests/test_archive.py -q`. Expected: PASS.
- [ ] **Step 5: Commit.** Message: `feat: archive merge with rounds, price drops, archiving rules`.

### Task 3: Polite HTTP client + Gdańsk source

**Files:**
- Create:
  - `src/przetargi/http.py`
  - `src/przetargi/sources/__init__.py`
  - `src/przetargi/sources/gdansk.py`
- Fixtures:
  - `tests/fixtures/gdansk/list.html` (from https://gdansk.pl/urzad-miejski/ogloszenia-o-przetargach,a,1439)
  - `tests/fixtures/gdansk/2026-10-26.pdf` (https://download.cloudgdansk.pl/gdansk-pl/d/202608280300/ogloszenie-o-przetargach-nieograniczonych-planowanych-na-dzien-26-10-2026.pdf)
  - `tests/fixtures/gdansk/wykaz.html` (one current page from the gminne wykazy section `,a,1432`, and the Skarb Państwa section `,a,1437` if it lists flats)
- Test: `tests/test_gdansk.py`

**Interfaces:**
- **Produces, `http.py`:**
  - `class PoliteClient` with `__init__(min_delay=1.0)`, `get(url) -> httpx.Response` and `get_bytes(url) -> bytes`.
  - It sends the UA from Global Constraints and keeps per-host delays.
  - It checks robots.txt through `urllib.robotparser`, cached per host. A disallowed URL raises `RobotsDisallowed`.
- **Produces, `sources/__init__.py`:**
  - `@dataclass Source(name: str, fetch: Callable[[PoliteClient], list[Offer]])`
  - `SOURCES: list[Source]`. Each later task appends its own source.
- **Produces, `gdansk.py`:**
  - `parse_list(html: str, base_url: str) -> list[str]`: the URLs of auction articles.
  - `parse_article(html: str, base_url: str) -> list[str]`: the PDF URLs.
  - `parse_auction_pdf(pdf_bytes: bytes, notice_url: str) -> list[Offer]`.
  - `parse_wykaz(html_or_text: str, notice_url: str) -> list[Offer]`: offers with status `planned`.
  - `fetch(client) -> list[Offer]`.
  - Source name `"um-gdansk"`, city `"Gdańsk"`.

- [ ] **Step 1: Save the fixtures** with `curl -A "przetargi-monitor/1.0" -o …` for the URLs above. Open each PDF or page once to note what each property's table row looks like.
- [ ] **Step 2: Write the failing tests.**

```python
def test_gdansk_pdf_finds_known_flats():
    offers = parse_auction_pdf(FIX/"2026-10-26.pdf".read_bytes(), "https://x/n.pdf")
    by_addr = {normalise_address(o.address): o for o in offers}
    assert by_addr[normalise_address("Uczniowska 37/4")].start_price == 500000
    assert by_addr[normalise_address("Góreckiego 8/3,4A")].start_price == 720000
    assert by_addr[normalise_address("Lenartowicza 3/5")].start_price == 300000
    for o in offers:
        assert o.status == "auction" and o.auction_date == "2026-10-26"
        assert o.type in ("flat", "house") and o.city == "Gdańsk"
        assert o.area_m2 is None or 10 < o.area_m2 < 500
        assert o.deposit is None or o.deposit < o.start_price

def test_gdansk_pdf_keeps_only_residential():
    # every non-residential item in the fixture PDF (land, lokal użytkowy) is absent
    ...  # assert the count equals the number of residential items you counted in Step 1

def test_gdansk_list_and_article_links():
    assert any(",a," in u for u in parse_list(FIX/"list.html".read_text(...), BASE))

def test_gdansk_wykaz_planned():
    offers = parse_wykaz(...)
    assert all(o.status == "planned" for o in offers)
```

- [ ] **Step 3: Run** `uv run pytest tests/test_gdansk.py -q`. Expected: FAIL.
- [ ] **Step 4: Implement `http.py` and `gdansk.py`.**
  - Use `pdfplumber` `extract_tables()` first. If the tables come out broken, fall back to `extract_text(layout=True)` and split on the item numbering.
  - Classify each item with `classify_type` and drop `None`.
  - Take the date from the PDF title or heading via `parse_date`.
  - Set `source_id` to the PDF filename plus the item number.
- [ ] **Step 5: Run** `uv run pytest tests/test_gdansk.py -q`. Expected: PASS.
- [ ] **Step 6: Live smoke test** (one run, not part of the suite): `uv run python -c "from przetargi.http import PoliteClient; from przetargi.sources.gdansk import fetch; print(len(fetch(PoliteClient())))"`. Expected: the number is at least 1.
- [ ] **Step 7: Commit.** Message: `feat: Gdańsk auctions and wykazy source`.

### Task 4: Sopot source

**Files:**
- Create: `src/przetargi/sources/sopot.py`
- Fixtures:
  - `tests/fixtures/sopot/menu107.json` (`https://bip.sopot.pl/api/menu/107/articles?limit=50&offset=0`)
  - `article25322.json` (`/api/articles/25322`)
  - `article25322.txt`: the text of its .doc attachment, converted once with antiword, or by hand if antiword isn't on Windows
  - `menu117.json`
- Test: `tests/test_sopot.py`

**Interfaces:**
- **Consumes:** `PoliteClient`, `textutil`, `Source` registry.
- **Produces:**
  - `classify_title(title: str) -> Literal["sale","cancel","skip"]`
  - `parse_menu(json_text: str) -> list[tuple[int, str]]`: (id, title) pairs.
  - `parse_article(article_json: str, attachment_text: str|None) -> Offer|None`
  - `doc_to_text(data: bytes) -> str|None`: runs `antiword` through subprocess. Returns None when antiword is missing.
  - `fetch(client) -> list[Offer]`
  - Source name `"um-sopot"`, city `"Sopot"`.
  - Menu 107 gives auction items. Menu 117 gives `planned` items.
  - Page through with `offset` until an empty page or 200 items.
- **Price fallback:** when antiword is missing, the price and area come from the article HTML text if present, and otherwise stay `None`.

- [ ] **Step 1: Save the fixtures** with curl.
- [ ] **Step 2: Write the failing tests.**
  - `test_sopot_classify_titles`:
    - "II publiczny przetarg ustny nieograniczony na sprzedaż lokalu mieszkalnego nr 1 …" → `sale`
    - "… najem …" → `skip`
    - "… ROZSTRZYGNIĘTY" → `skip`
    - "Odwołanie przetargu …" → `cancel`
  - `test_sopot_article_25322`: address normalises to `armii krajowej 61/1`, `type == "flat"`, `status == "auction"`, `auction_date == "2026-10-26"`, and `start_price` is an int > 0 (read from the attachment text).
  - `test_sopot_menu_parses_ids`: the result is not empty and contains `25322`.
- [ ] **Step 3: Run** `uv run pytest tests/test_sopot.py -q`. Expected: FAIL.
- [ ] **Step 4: Implement `sopot.py`.**
- [ ] **Step 5: Run** `uv run pytest tests/test_sopot.py -q`. Expected: PASS.
- [ ] **Step 6: Commit.** Message: `feat: Sopot BIP source`.

### Task 5: PKP and AMW sources

**Files:**
- Create:
  - `src/przetargi/sources/pkp.py`
  - `src/przetargi/sources/amw.py`
- Fixtures:
  - `tests/fixtures/pkp/list_gdansk.html` (`https://www.pkp.pl/pl/sprzedaz?menu=2` with the Pomorskie/residential filters, as found in the browser)
  - `tests/fixtures/pkp/offer.html` (the Elbląska 89/1 offer page)
  - `tests/fixtures/amw/list.html` (the search results page filtered to region Gdynia, flat/house)
- Test:
  - `tests/test_pkp.py`
  - `tests/test_amw.py`

**Interfaces:**
- **Produces, `pkp.py`:**
  - `parse_list(html) -> list[str]`: offer URLs.
  - `parse_offer(html, url) -> Offer|None`
  - `fetch(client)`
  - Source name `"pkp"`.
- **Produces, `amw.py`:**
  - `parse_list(html, base_url) -> list[Offer]`
  - `fetch(client)`
  - Source name `"amw"`.
- **Both:**
  - keep only offers where `canonical_city(...)` is not None and `classify_type(...)` is not None
  - set `photo_url` to the first gallery image's absolute URL when one exists
  - set `source_id` from the site's numeric id
  - never fetch AMW `/uploads/*.pdf`

- [ ] **Step 1: Save the fixtures.**
- [ ] **Step 2: Write the failing tests.**
  - `test_pkp_elblaska`: `start_price == 260000`, `city == "Gdańsk"`, `type == "flat"`, and normalised address `elblaska 89/1`.
  - `test_pkp_list_finds_offers`.
  - `test_amw_filters_area`: every parsed offer has `canonical_city` in AREA. An item in Słupsk, if the fixture has one, is excluded.
  - `test_amw_photo_absolute`: every `photo_url` that is not None starts with `https://`.
- [ ] **Step 3: Run** the tests. Expected: FAIL.
- [ ] **Step 4: Implement both sources.**
- [ ] **Step 5: Run** the tests. Expected: PASS.
- [ ] **Step 6: Commit.** Message: `feat: PKP and AMW sources`.

### Task 6: Geocoding

**Files:**
- Create: `src/przetargi/geocode.py`
- Test: `tests/test_geocode.py`

**Interfaces:**
- **Produces:** `geocode_all(offers: dict[str, Offer], cache: dict[str, list[float]|None], lookup: Callable[[str], tuple[float,float]|None]) -> None`.
  - It sets `lat`/`lng` in place for offers whose `"{address}, {city}, Polska"` is resolvable.
  - The cache stores misses as `None`, so a miss isn't retried every day.
  - Skip offers with an empty address.
- **Produces:** `nominatim_lookup(client: PoliteClient) -> Callable`.
  - Endpoint: `https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=pl&q=…`
  - Waits at least 1 s between calls (`PoliteClient(min_delay=1.0)`).

- [ ] **Step 1: Write the failing tests** using a fake `lookup`:
  - `test_geocode_uses_cache`: a cached address does not call lookup.
  - `test_geocode_caches_miss`: a `None` result is cached as `None`, and the offer keeps `lat is None`.
- [ ] **Step 2: Run** the tests. Expected: FAIL. **Step 3: Implement.** **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit.** Message: `feat: Nominatim geocoding with cache`.

### Task 7: Market comparison

**Files:**
- Create: `src/przetargi/market.py`
- Fixtures:
  - `tests/fixtures/market/valuation.json`: run `deweloperuch valuation estimate --lat 54.37 --lng 18.6 --area 48 --limit 3 --json` once
  - `tests/fixtures/market/transactions_gdansk.json`: `deweloperuch stats transactions gdansk --json`
- Test: `tests/test_market.py`

**Interfaces:**
- **Consumes:** `Offer`, `AREA` slugs.
- **Produces:**
  - `class Stopped(Exception)`
  - `run_cli(args: list[str]) -> dict`:
    - runs `["deweloperuch", *args, "--json"]` via subprocess
    - exit 3 → raise `Stopped(stderr)`
    - any other non-zero exit → raise `RuntimeError`
  - `city_median(transactions_json: dict, today: str) -> tuple[int, str]|None`: returns the median price/m² and its period.
    - Use the period equal to `last_complete_period` if that field is present.
    - Otherwise use the newest period at least 3 months before `today`.
  - `apply_market(offers, cache: dict, cli=run_cli, today: str) -> str|None`:
    - Returns None, or the warning `"market data unavailable"` after `Stopped`.
    - Applies only to flats with `start_price`.
    - **Nearby:** if `lat`, `lng` and `area_m2` are set, use cache key `f"{key}|{start_price}|{area_m2}"` → `valuation estimate`. Then `gap = (start_price / estimated_value - 1) * 100`, `basis = "nearby"`, `low_confidence` copied from the result, and `period = f"{period_months} mies."`.
    - **City median otherwise:** use `price_per_m2` against `city_median`, fetched once per city per run, with `basis = "city_median"`.
    - Houses keep `None` for every market field.
    - After `Stopped`: make no further CLI calls, and keep values already cached.

- [ ] **Step 1: Save the two fixtures.** Use `uvx --from deweloperuch-mcp deweloperuch …`, one command at a time.
- [ ] **Step 2: Write the failing tests** with a fake `cli`:
  - `test_market_nearby_gap`: the gap is computed from `estimated_value` in the fixture. Check `round(gap,1)` against a hand-calculated value.
  - `test_market_city_median_fallback`: with no lat, `basis == "city_median"`.
  - `test_market_houses_skipped`.
  - `test_market_stop_halts_calls`: the fake raises `Stopped` on the first call. Expect 1 call in total, warning `"market data unavailable"`, and other offers unchanged.
  - `test_market_cache_hit_no_call`.
  - `test_city_median_period`: use the fixture JSON.
- [ ] **Step 3: Run** the tests. Expected: FAIL. **Step 4: Implement.** **Step 5: Run** the tests. Expected: PASS.
- [ ] **Step 6: Commit.** Message: `feat: market comparison via deweloperuch`.

### Task 8: Orchestrator

**Files:**
- Create: `src/przetargi/run.py`
- Test: `tests/test_run.py`

**Interfaces:**
- **Consumes:**
  - `SOURCES`, `PoliteClient`
  - from `archive`: `load`, `merge`, `save`
  - `geocode_all`, `nominatim_lookup`
  - `apply_market`
  - `render_site` (Task 9)
- **Produces:**
  - `run(data_dir: Path, site_dir: Path, today: str, sources=SOURCES, client=None, geocode_lookup=None, market_cli=None) -> list[SourceStatus]`
  - `main()`, so that `python -m przetargi.run` uses `data/` and `site/` and today's date in Europe/Warsaw.
- **Behaviour:**
  1. Fetch each source inside try/except. On failure, record a `SourceStatus(ok=False, error=str(e)[:300])` and skip the merge for that source. A count of 0 records `ok=True` with `warning="0 items: format changed?"`.
  2. Save `offers.json` and `status.json`.
  3. Geocode, then save `geocode.json`.
  4. Apply the market comparison, then save `market.json`. Any market warning goes into a `SourceStatus(source="deweloperuch", …)`.
  5. Render.

- [ ] **Step 1: Write the failing tests** with fake sources and fakes for geocode and cli:
  - `test_run_isolates_failing_source`: source A raises and source B returns 1 offer. Expect B merged, A's status `ok=False`, and A's previously archived rows still present.
  - `test_zero_items_is_warning`.
  - `test_run_writes_files`: `offers.json`, `status.json` and `site/index.html` exist.
- [ ] **Step 2: Run** the tests. Expected: FAIL. **Step 3: Implement.** **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit.** Message: `feat: daily run orchestrator`.

### Task 9: Page rendering

**Files:**
- Create:
  - `src/przetargi/render.py`
  - `src/przetargi/templates/index.html.j2`
  - `src/przetargi/static/app.js`
  - `src/przetargi/static/app.css`
- Test: `tests/test_render.py`

**Interfaces:**
- **Produces:**
  - `render_site(offers: dict[str, Offer], statuses: list[SourceStatus], today: str, site_dir: Path) -> None`. It writes `site/index.html` and inlines the CSS and JS.
  - The data is embedded as `<script id="data" type="application/json">`, with a `new` flag (`first_seen == today`) and an `archived` flag (`is_archived`) on each row.
  - `maps_url(o) -> str`: `https://www.google.com/maps/search/?api=1&query=` + URL-encoded `f"{address}, {city}"`.
  - `streetview_url(o) -> str|None`: `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lng}` when there are coordinates. Otherwise None, and the page links `maps_url` instead.

**Page (mockup B):**
- Header: last updated, number of active offers, number of new offers, and one status line per source (failed sources in red with the error).
- Tabs: Aktywne / Archiwum.
- Filters: a city `<select>`, flat/house, status, and "tylko nowe".
- Table columns: Status · Data przetargu · Adres (maps link) · Miasto · Typ · m² · Cena wywoławcza · zł/m² · vs rynek · Wadium · Zdjęcie · Źródło.
- Sorting: click a header to sort. Numbers sort numerically, and nulls always go last.
- New rows have a left edge in the accent colour. A price drop shows "↓" next to the price, with a tooltip of the rounds.
- The "vs rynek" cell shows `−18%` in green when negative. It gets a `≈` prefix when `market_low_confidence` is true. Its tooltip names the basis and period.
- Below the table: a "Sprawdź ręcznie" box with the four links from Global Constraints. Then the exact footer text.
- Phone width: the table sits in an `overflow-x:auto` wrapper.
- Light and dark themes via `prefers-color-scheme`.

- [ ] **Step 1: Write the failing tests:**
  - `test_render_contains_rows_and_links`: a sample offer → the HTML contains its maps URL, the source link, and the footer text exactly.
  - `test_maps_url_encoding`: the address `Góreckiego 8/3,4A` is URL-encoded.
  - `test_streetview_fallback`.
  - `test_failed_source_shown`.
- [ ] **Step 2: Run** the tests. Expected: FAIL. **Step 3: Implement.** **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Local end-to-end check.** Run `uv run python -m przetargi.run` (live, once), then open `site/index.html` in a browser. Expected:
  - the Gdańsk rows (Uczniowska, Góreckiego, Lenartowicza) and the PKP Elbląska row are present
  - sorting and filters work
  - all sources show ok, or show a clear error
- [ ] **Step 6: Commit,** including the first `data/*.json`. Message: `feat: static page`.

### Task 10: GitHub repository, daily workflow, Pages

**Files:**
- Create: `.github/workflows/daily.yml`, `README.md` (3–5 lines: what the project is, the page URL, how to run it locally).

**The workflow:**
- Triggers: `schedule: cron "0 4 * * *"` and `workflow_dispatch`.
- Permissions: `contents: write`, `pages: write`, `id-token: write`.
- Concurrency group `daily`.
- Steps:
  1. checkout
  2. `sudo apt-get install -y antiword`
  3. `astral-sh/setup-uv`
  4. `uv sync`
  5. `uv run pytest -q`
  6. `uv run python -m przetargi.run`
  7. commit `data/` if it changed (as `github-actions[bot]`, message `data: YYYY-MM-DD`) and push
  8. `actions/upload-pages-artifact` with path `site`
  9. `actions/deploy-pages`

- [ ] **Step 1: Prerequisite.** The owner must have run `gh auth refresh -s workflow`. Check with `gh auth status`: the scopes must include `workflow`. If they don't, stop and ask.
- [ ] **Step 2: Write `daily.yml` and `README.md`.** Commit them with the message `ci: daily run and Pages deploy`.
- [ ] **Step 3: Create the repo and push.** Run `gh repo create cavkie/przetargi --public --source . --push`.
- [ ] **Step 4: Enable Pages from Actions.** Run `gh api -X POST repos/cavkie/przetargi/pages -f build_type=workflow`. If it already exists, use PUT instead.
- [ ] **Step 5: First run.** Run `gh workflow run daily.yml`, then `gh run watch`. Expected:
  - the run succeeds
  - https://cavkie.github.io/przetargi/ shows the table
  - a `data: …` commit appears

---

## Self-review notes

- **Spec coverage:**
  - sources → Tasks 3–5
  - wykazy as planned → Tasks 3 and 4
  - one row per property, archive rules → Task 2
  - Nominatim → Task 6
  - market comparison and STOP → Task 7
  - failure visibility → Task 8
  - page with maps, Street View, photos, check-by-hand box and footer → Task 9
  - public Pages and cron → Task 10
- **Out of scope by spec:** scraping protected portals, house valuation, notifications.
