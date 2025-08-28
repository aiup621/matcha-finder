import os, sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from cache_utils import EnvConfig, Cache

def test_cache_namespace_changes():
    os.environ["CACHE_VERSION"] = "v9"
    env = EnvConfig()
    c1 = Cache(env, phase=1)
    c2 = Cache(env, phase=3)
    assert env.CACHE_VERSION in c1.namespace()
    assert c1.namespace() != c2.namespace()
    c3 = Cache(env, phase=3, cache_bust=True)
    c4 = Cache(env, phase=3, cache_bust=True)
    assert c3.namespace() != c4.namespace()
