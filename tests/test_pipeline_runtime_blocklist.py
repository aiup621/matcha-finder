import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from runtime_blocklist import RuntimeBlockList, requires_js


def test_runtime_blocklist_learns_domain():
    rb = RuntimeBlockList()
    url1 = "http://example.com/a"
    url2 = "http://example.com/b"
    rb.record(url1, "no_html")
    assert not rb.is_blocked(url1)
    rb.record(url2, "status_403")
    assert rb.is_blocked(url1)
    assert rb.is_blocked("http://example.com/c")
    assert not rb.is_blocked("http://other.com")


def test_requires_js_heuristic():
    html = "<html>" + "<script>1</script>" * 200 + "</html>"
    assert requires_js(html)
    assert not requires_js("<html><body>hi</body></html>")
