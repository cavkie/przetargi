# Przetargi Trójmiasto

A daily list of flats and houses for sale by public bodies in Gdańsk, Sopot and nearby towns: city auctions and planned sales (wykazy), PKP and AMW. Flats are compared with RCN sale prices from deweloperuch.pl.

Page: https://cavkie.github.io/przetargi/

A GitHub Actions job runs every morning, stores the archive in `data/` and publishes `site/`. To run it locally: `uv sync && uv run python -m przetargi.run`, then open `site/index.html`.
