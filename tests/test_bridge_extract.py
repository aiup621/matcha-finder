import pipeline_smart as ps


def test_extract_yelp():
    html = '<a href="https://examplecafe.com">Website</a>'
    res = ps.extract_official_site_from_bridge(html, 'https://www.yelp.com/biz/foo')
    assert 'https://examplecafe.com' in res


def test_extract_toasttab():
    html = '<a href="https://examplecafe.com" class="website">Website</a>'
    res = ps.extract_official_site_from_bridge(html, 'https://toasttab.com/bar')
    assert 'https://examplecafe.com' in res


def test_extract_instagram():
    html = '{"external_url":"https://examplecafe.com"}'
    res = ps.extract_official_site_from_bridge(html, 'https://instagram.com/foo')
    assert 'https://examplecafe.com' in res
