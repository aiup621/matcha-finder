import os
import tempfile
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from persistent_cache import PersistentCache


def test_seen_and_record():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "cache.sqlite")
        pc = PersistentCache(path)
        assert pc.seen("http://example.com") is None
        pc.record("http://example.com", "skip", "test")
        assert pc.seen("http://example.com") == "skip"
        pc.record_add("http://example.com", "Example")
