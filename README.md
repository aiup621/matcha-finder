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
