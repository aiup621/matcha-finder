import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from blocklist import load_domain_blocklist, is_blocked_domain


def test_blocklist_wildcard():
    patterns = load_domain_blocklist('config/domain_blocklist.txt')
    assert is_blocked_domain('http://facebook.com/page', patterns)
    assert is_blocked_domain('http://a.square.site', patterns)
    assert is_blocked_domain('http://square.site', patterns)
    assert not is_blocked_domain('http://example.com', patterns)
