import requests

feeds = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
]
headers = {"User-Agent": "Mozilla/5.0"}
for url in feeds:
    r = requests.get(url, headers=headers, timeout=10)
    print(url[:60], r.status_code, r.text[:400])
    print()
