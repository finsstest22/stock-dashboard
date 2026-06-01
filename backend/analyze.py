import requests
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

res = requests.get("https://www.indexergo.com/", headers=headers)
print(f"Status: {res.status_code}")

soup = BeautifulSoup(res.text, "html.parser")

# 주요 지표 영역 탐색
print("\n=== 텍스트 샘플 (처음 3000자) ===")
print(res.text[:3000])
