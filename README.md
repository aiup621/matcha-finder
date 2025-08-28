# Matcha Finder

Utilities for discovering matcha-serving cafes and collecting contact info.

## Query limits

`pipeline_smart.py` issues Google CSE queries to discover new sites. To prevent
excessive usage, the script caps the number of queries per execution. The default
is 120 queries, but it can be adjusted by setting the `MAX_QUERIES_PER_RUN`
environment variable:

```bash
export MAX_QUERIES_PER_RUN=80
python pipeline_smart.py
```

Lowering this value is useful to avoid hitting API limits or generating too many
requests in a single run.

## Domain blocklist and cache

Before fetching a URL the crawler checks `config/domain_blocklist.txt` and a
persistent cache stored under `.cache/`.  Domains listed in the blocklist or
previously marked as blocked are skipped immediately.  The cache also stores
hosts and URLs that have already been visited so that re-runs avoid processing
the same sites.  The cache persists between GitHub Actions runs thanks to
`actions/cache`.

Set `CLEAR_CACHE=1` to ignore existing cache data and rebuild it from scratch.

## Query tuning

Search queries are now built via `build_query()`, which injects intent terms and
excludes common noise domains.  The function combines seed information such as
`city` or `state` with the intent boost terms
(`latte`, `menu`, `hours`, `about`, `story`, `店舗情報`, `メニュー`).  You can customise
the negative sites and intent terms by editing `config/settings.yaml`.

### Options

* `SKIP_THRESHOLD` – rotate to the next seed after this many consecutive skips
  (default 15).
* `CLEAR_CACHE` – clear `.cache` on start when set to `1`.

The blocklist and intent settings are stored in `config/settings.yaml`.
