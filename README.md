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
the same sites.  The cache persists between runs using `actions/cache`, and a
SQLite database `.cache/crawler.sqlite` stores visit results and skip reasons
for long-term avoidance.

Set `CLEAR_CACHE=1` to ignore existing cache data and rebuild it from scratch.

## Query tuning

Search queries are now built via `smart_search.QueryBuilder`, which injects
intent terms and excludes common noise domains.  Configuration lives in
`config/query_intent.json` and can be overridden via environment variables.

### Environment variables

| Variable | Description |
| --- | --- |
| `EXCLUDE_DOMAINS` | Comma-separated extra domains to block before fetching. |
| `EXCLUDE_DOMAINS_EXTRA` | Additional domains appended to the default blocklist. |
| `CACHE_VERSION` | Cache namespace version prefix (default `v1`). |
| `SKIP_ROTATE_THRESHOLD` | Consecutive skip count before query rotation (default 8). |
| `MAX_ROTATIONS_PER_RUN` | Maximum number of query rotations per run (default 4). |
| `CITY_SEEDS` | Optional comma-separated list of city, state pairs. |
| `BLOCKLIST_FILE` | Path to domain blocklist file. |
| `INTENT_FILE` | Path to query intent configuration. |
| `CLEAR_CACHE` | Clear `.cache` on start when set to `1`. |
| `FORCE_ENGLISH_QUERIES` | Force query builder to emit ASCII-only queries (default `0`). |
| `CACHE_BURST_THRESHOLD` | Cache hit ratio triggering temporary cache bypass (default `0.5`). |
| `SEARCH_RADIUS_KM` | Base radius in kilometres for nearby city expansion (default `25`). |

These options allow customising search behaviour without modifying the code.

### Rotation behaviour

`pipeline_smart.py` rotates search queries when consecutive skips exceed
`SKIP_ROTATE_THRESHOLD`. Rotations cycle through cities, add synonym terms and
optionally tighten context to `menu|hours|contact`. The number of rotations is
capped by `MAX_ROTATIONS_PER_RUN`.

Runs may end with `0` additions if all rotations fail to produce acceptable
candidates. Adjust `SKIP_ROTATE_THRESHOLD` or provide a custom `CITY_SEEDS` list
to explore different regions.
