import os
from datetime import datetime, timedelta
import sys, pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from crawler_cache import load_cache, save_cache, mark_seen, has_seen


def test_cache_persist_ttl(tmp_path, monkeypatch):
    cache_dir = tmp_path / 'cache'
    monkeypatch.setenv('CACHE_DIR', str(cache_dir))
    monkeypatch.delenv('CLEAR_CACHE', raising=False)

    cache = load_cache(clear=True)
    mark_seen(cache, 'http://example.com/page')
    save_cache(cache)

    cache2 = load_cache()
    assert has_seen(cache2, 'http://example.com/page')

    old_date = (datetime.utcnow() - timedelta(days=31)).date().isoformat()
    cache2['seen_urls']['http://old.com'] = old_date
    cache2['seen_hosts']['old.com'] = old_date
    save_cache(cache2)

    cache3 = load_cache()
    assert 'http://old.com' not in cache3['seen_urls']
    assert 'old.com' not in cache3['seen_hosts']

    monkeypatch.setenv('CLEAR_CACHE', '1')
    cache4 = load_cache()
    assert cache4['seen_urls'] == {}
