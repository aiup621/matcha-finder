# Troubleshooting

Common skip reasons reported by `pipeline_smart.py` and how to resolve them.

| Reason | Meaning | Possible fix |
| --- | --- | --- |
| `blocked_domain` | URL's domain is on the blocklist. | Remove from `EXCLUDE_DOMAINS` or blocklist file if needed. |
| `snippet_not_matcha_context` | Search snippet lacks matcha context. | Broaden query or adjust city seeds. |
| `no_html` | Prefetch detected non-HTML content. | Ensure the URL points to an HTML page. |
| `no matcha evidence` | Site content doesn't mention matcha. | Verify manually or skip the site. |
| `not US independent cafe` | Site appears outside the US or is not a cafe. | Limit queries to US cities. |
| `no contacts found` | No contact info discovered. | Add contact info to the site or adjust `REQUIRE_CONTACT_ON_SNIPPET`. |
