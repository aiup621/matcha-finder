import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from crawler.control import RunState, format_stop


def test_cache_hits_do_not_stop():
    st = RunState(target=3, max_queries=10, max_rotations=2, skip_rotate_threshold=2, cache_burst_threshold=0.5)
    for _ in range(5):
        st.queries += 1
        st.record_skip("cache-hit")
        stop, _ = st.should_stop()
        assert not stop
    for _ in range(3):
        st.record_add()
    stop, reason = st.should_stop()
    assert stop and reason == "target_met"


def test_rotation_limit_soft():
    st = RunState(target=3, max_queries=10, max_rotations=1, skip_rotate_threshold=2)
    st.record_skip("cache-hit")
    st.record_skip("cache-hit")
    assert st.should_rotate() is True
    st.record_skip("cache-hit")
    st.record_skip("cache-hit")
    assert st.should_rotate() is False
    stop, _ = st.should_stop()
    assert not stop


def test_stop_message_format():
    st = RunState(target=3, max_queries=10, max_rotations=4, skip_rotate_threshold=2)
    st.queries = 5
    st.added = 3
    msg = format_stop("target_met", st)
    assert msg == "[STOP] reason=target_met added=3/3 rotations=0/4 queries=5/10"
