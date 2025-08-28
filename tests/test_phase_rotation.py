import sys, os, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from crawler.control import RunState
from cache_utils import EnvConfig, Cache


def test_phase_and_namespace_rotation():
    os.environ["SKIP_ROTATE_THRESHOLD"] = "8"
    try:
        env = EnvConfig()
        state = RunState(target=1, max_queries=100, max_rotations=5, skip_rotate_threshold=env.SKIP_ROTATE_THRESHOLD)
        cache1 = Cache(env, phase=state.phase)
        for _ in range(env.SKIP_ROTATE_THRESHOLD):
            state.record_skip("miss")
        if state.should_rotate():
            state.escalate_phase()
        assert state.phase == 2
        for _ in range(env.SKIP_ROTATE_THRESHOLD):
            state.record_skip("miss")
        if state.should_rotate():
            state.escalate_phase()
        assert state.phase == 3
        cache3 = Cache(env, phase=state.phase)
        assert cache1.namespace() != cache3.namespace()
    finally:
        del os.environ["SKIP_ROTATE_THRESHOLD"]
