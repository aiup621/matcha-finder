# Matcha Finder

Collects cafe websites from OpenStreetMap and checks whether they serve matcha and provide contact options.

## Setup

1. **Python 3.11**
2. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
3. Fill `data/countries.txt` with ISO‑2 country codes (one per line).
4. Configure GitHub Action secrets (`Settings → Secrets and variables → Actions`):
   - `GOOGLE_API_KEY` – Programmable Search API key (leave empty to skip fallback search)
   - `GOOGLE_CX` – Programmable Search CX
   - Optional `SEARCH_BUDGET` – daily query limit

## Usage

Fetch and verify locally for a single country:

```bash
python src/overpass_fetch.py --country US --out data/seeds_US.csv
python src/verify_crawl.py --in data/seeds_US.csv --out data/results_US.csv
# Optional when API key and CX are provided
export GOOGLE_API_KEY=xxxx
export GOOGLE_CX=xxxx
python src/fallback_search.py --country US --budget 10
```

### Update contacts from an existing sheet

If a spreadsheet already contains home page URLs in column C, populate
contact fields for each entry:

```bash
export SHEET_ID=xxxx              # target spreadsheet
export ACTION_ROW=2               # starting row (default 2)
python update_contact_info.py
```

Column D will be filled with Instagram links, column E with contact
emails and column F with contact form URLs. When none of these are
found, column G is set to `"なし"`.

## GitHub Actions

The workflow in `.github/workflows/matcha.yml` runs daily and on manual dispatch. It processes each country, uploads `data/*.csv` as artifacts and, when running on `main`, commits updated results.

## Notes

- Respect robots.txt, rate limits and local laws.
- The crawler touches only a handful of lightweight paths and sleeps 0.3s per site.
- Google search fallback is optional and stops gracefully on quota errors.
- Common failures such as HTTP 429 or timeouts usually resolve after retrying later.
- Extracting contact information should be done with discretion; do not spam addresses found.
