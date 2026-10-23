# Przetargi monitor: Gdańsk & Sopot property auctions

Date: 2026-10-23
Owner: cavkie (GitHub)

## Intent

The owner wants to watch for flats and houses in Gdańsk and Sopot that may sell
below market price through public sales: city auctions, state bodies, bailiffs
(komornik), and bankruptcy trustees (syndyk). The information is public but
scattered across hard-to-search PDFs and portals, or sold by paid aggregators.

**The priority is complete coverage and a clean, readable format.** Each flat
is also compared with market sale prices (see "Market comparison").

The owner checks the page from several devices, so it must be online.

## Goals

- Every morning, collect flat and house sale notices for Gdańsk and Sopot from
  the free sources that can be read automatically (list below).
- Publish one clean page (layout "B", a sortable table) on GitHub Pages.
- Keep a permanent archive of every notice found, because the city sites remove
  old notices.
- Mark offers that are new since the previous run.
- List the bot-protected sources as links to check by hand.

## Owner's answers after review

- **Include wykazy as "planned".** Collect the Gdańsk and Sopot wykazy
  nieruchomości (lists of property set aside for sale): Gdańsk
  `wykazy-nieruchomosci-gminnych,a,1432` and the Skarb Państwa list `,a,1437`;
  Sopot BIP menu `m,117`. They become rows with status "planned", usually with
  no price or date. When the auction notice for the same property appears, the
  row becomes an auction instead of a duplicate row being added.
- **Include nearby towns.** Area = Gdańsk, Sopot, Gdynia, Pruszcz Gdański (town
  and gmina), Kolbudy, Żukowo and Rumia. The exact list is Claude's call. The
  nearby towns come only from the regional sources (PKP, AMW). Their own city
  halls are not scraped in v1; Gdynia's city site is a likely next addition.
  The page gets a city filter instead of only Gdańsk/Sopot chips.

- **Include a price comparison to the market in v1.** Details below under
  "Market comparison".

## Market comparison

Data comes from deweloperuch.pl, a community-run site of sale prices from the
official price register (RCN), read with the `deweloperuch` CLI
(`pip install deweloperuch-mcp`).

- **Flats with a known area and position:** run
  `deweloperuch valuation estimate --lat --lng --area --json` once per property
  and cache the result in `data/market.json`. Each property is valued once;
  re-value it only when its price or area changes. Show the gap as a percentage:
  starting price compared with the estimated value. When the result has
  `low_confidence: true` (fewer than 5 comparable sales), mark the gap with a
  "≈" and a tooltip.
- **Flats without a position, or when a valuation fails:** compare the price per
  m² with the city's median sale price per m² from
  `deweloperuch stats transactions <city> --json`. Use the last complete month
  (`last_complete_period`). Fetch it once per city per run. Mark this comparison
  as "city median".
- **Houses:** the CLI has no house valuation, so v1 shows "—" with a note.
  (Claude's call. Revisit if a free house-price source turns up.)
- **Tooltip:** every gap says where it came from (nearby valuation or city
  median) and the period.
- **Page footer:** "an estimate, not an appraisal; not financial advice".
- **Being polite:** run CLI commands one at a time; each run sends at most a few
  dozen requests. If the CLI exits with code 3 (STOP), make no more deweloperuch
  calls in that run and show "market data unavailable" on the page. Never lift
  a STOP automatically.
- **Table:** a "vs market" column, sortable. Negative values (below market) are
  shown in green.

## Non-goals (v1)

- Scraping bot-protected portals (licytacje.komornik.pl, elicytacje.mf.gov.pl,
  krz.ms.gov.pl).
- A market comparison for houses (no data source in the CLI).
- Notifications (email or push).
- Land, commercial premises, garages and rentals.

## Anti-goals

- **No hammering or evasion.** Do not try to get around any site's bot
  protection. Send one polite pass a day, with a clear User-Agent.
- **No silent losses.** If a source fails or its format changes, the page must
  say so ("Sopot: failed to read on 2026-10-24") instead of quietly showing
  fewer offers.
- **No made-up values.** A field that can't be parsed shows "—" and a link to the
  notice. Never guess areas or prices.

## Sources

| Source | Where | How to read | Notes |
|---|---|---|---|
| UM Gdańsk, Wydział Skarbu (city and Skarb Państwa sales) | https://gdansk.pl/urzad-miejski/ogloszenia-o-przetargach,a,1439 | A static HTML list of articles (`…,a,<id>`), each linking to a PDF on download.cloudgdansk.pl | About monthly, 2–3 flats per auction day. No RSS. PDF tables are wide, so use layout-aware text extraction. Keep only flats (lokal mieszkalny) and houses (nieruchomość zabudowana budynkiem mieszkalnym). |
| UM Sopot BIP | `https://bip.sopot.pl/api/menu/107/articles?limit=N&offset=M`, then `/api/articles/<id>` | A JSON API. The HTML site is an empty JavaScript shell. | Keep titles about the sale of a flat or residential building. Exclude rentals (najem) and finished tenders (ROZSTRZYGNIĘTY / ZAKOŃCZONY). Details are often in a .doc attachment. |
| PKP S.A., Gdańsk branch | https://www.pkp.pl/pl/sprzedaz?menu=2 (GET filters `city`, `category1_id`, `strona`, `page_size`); offers at `?show=<id>` | HTML | Usually has a few Gdańsk flats. Offers often include photos. |
| AMW (Agencja Mienia Wojskowego) | https://amw.com.pl/pl/nieruchomosci/przetargi-nieruchomosci, with filters for flat or house and city | HTML | Has no Gdańsk/Sopot listings today, but is cheap to watch. robots.txt disallows `/uploads/*.pdf`, so read only the HTML. Offers often include photos. |

**Check by hand** (links only, shown in a box below the table):

- Bailiff auctions: https://licytacje.komornik.pl (Pomorskie → Gdańsk/Sopot, real estate)
- Tax-office auctions: https://elicytacje.mf.gov.pl
- Bankruptcy trustee notices: https://krz.ms.gov.pl (Gdańsk cases `GD1G/GUp/…`)
- Trustee offers re-posted on classifieds sites, e.g. tabelaofert.pl (optional link)

## The page

The page is a static site on GitHub Pages (public, which the owner accepted).
It follows mockup B: https://claude.ai/artifact/KKDuZfsN3ypMR37vfcJXLf

- **Header:** last updated time, number of active offers, number of new offers,
  and a status line per source (ok / failed).
- **Status column:** planned (wykaz) / auction / rokowania / cancelled.
- **Table columns:** status · auction date · address (link to Google Maps) · city · type
  (flat/house) · area m² · starting price · zł/m² · vs market · deposit · photo (a thumbnail
  when the source has one; otherwise a Street View link) · source (link to the
  original notice).
- **Behaviour:** click a column header to sort. Filter chips: Gdańsk / Sopot /
  flats / houses / new only. New offers have a highlighted left edge.
- **Tabs:** "Active" (auction date today or later, or no date) and "Archive"
  (past auctions).
- **Phones:** the table scrolls sideways inside its own container.
- **Language:** Polish addresses and terms with a simple UI (the owner reads both
  English and Polish). (Builder's call on UI language; English matches the
  mockup.)
- **Maps:** the address link is
  `https://www.google.com/maps/search/?api=1&query=<street, number, city>`.
  Street View uses `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=<lat>,<lng>`
  when coordinates are known; otherwise use the search link.

## How it runs

- **GitHub repository** `cavkie/przetargi` (public), set up in
  `E:\mieszkania\przetargi`.
- **GitHub Actions** cron runs every day at about 06:00 Europe/Warsaw (04:00
  UTC), and can also be started by hand.
- **Steps:**
  1. Fetch each source.
  2. Parse it into a common record.
  3. Merge into `data/offers.json`. This is the archive: never delete; update
     `last_seen`.
  4. Render the static HTML into `site/`.
  5. Commit the data and deploy Pages.
- **One failing source must not stop the others.** Its status is recorded and
  shown on the page.
- **Common record:** `id` (source + source id), `source`, `city`, `type`, `address`,
  `area_m2`, `start_price`, `price_per_m2`, `deposit`, `auction_date`,
  `auction_kind` (przetarg ustny / pisemny / rokowania), `notice_url`,
  `photo_url`, `first_seen`, `last_seen`, `raw_title`.
- **Being polite:** a single run sends a small number of requests with pauses,
  a User-Agent that names the project, and respects robots.txt.

## Decisions (made by Claude; the owner can override)

- Python on GitHub Actions; `uv` for dependencies.
- Static HTML with a small amount of plain JavaScript for sorting and filtering
  (no framework).
- The archive is kept in git as JSON. There is no database.
- PDF text is extracted with a layout-aware tool such as pdfplumber or
  `pdftotext -layout`. Sopot .doc files are converted with antiword or
  LibreOffice on the runner.
- "New" means `first_seen` is the date of the latest run.

- **One row per property, not per notice.** The key is source + normalised
  address. A second auction or rokowania for the same property updates that row
  and adds the new round to its price history. When the starting price drops,
  the row shows a "price drop" marker.
- **New and archived offers.** A row is "new" only the first time its property
  appears. A row moves to Archive when its auction date has passed, when it has
  a cancellation notice (odwołanie), or when it has not been seen at its source
  for 14 days.
- **No historical backfill.** The first run takes whatever each source lists at
  that moment. For Sopot that is every item the API returns, filtered. The
  archive grows from there.
- **Coordinates come from Nominatim (OpenStreetMap)**, at 1 request per second
  and cached permanently in `data/geocode.json`. They are used only for the
  Street View link. If geocoding fails, fall back to the map search link. Never
  show a guessed position as fact.

## Left to the builder

- The parsing details for each source, and a test fixture per source using real
  saved samples.
- The exact visual styling, within the mockup's direction.
- How to handle multi-item Gdańsk PDFs (one PDF, several properties). Each
  property becomes its own row, linking to the same PDF.

## Known setup needs

- The `gh` token lacks the `workflow` scope, which is needed to push
  `.github/workflows/*`. The owner runs `gh auth refresh -s workflow` once.
- Enable GitHub Pages (source: GitHub Actions) on the repository.
