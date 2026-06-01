import requests

urls = [
    "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
    "https://production.dataviz.cnn.io/index/fearandgreed/graphdata/past30",
]
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.cnn.com/markets/fear-and-greed",
    "Accept": "application/json",
}
for url in urls:
    r = requests.get(url, headers=headers, timeout=10)
    print(url, r.status_code, r.text[:300])
    print()
