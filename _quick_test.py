import sys; sys.path.insert(0, ".")
import pipeline
tests = [
    ("UE", "https://www.ubereats.com/store/xyz"),
    ("Menu path", "https://example.com/menu"),
    ("Official", "https://mycafe.example"),
]
for label, url in tests:
    print(f"{label} -> {pipeline.is_delivery_or_portal(url)}")