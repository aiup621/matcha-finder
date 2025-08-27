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

## Domain filters

Noise domains encountered during searches or crawling are centralized in
`matcha_finder/domain_filters.py`. Update `EXCLUDE_SITES` and `BLOCK_DOMAINS`
when logs show repeated false positives. Keep the lists alphabetized and commit
the change so both the query builder and extractor stay in sync.
