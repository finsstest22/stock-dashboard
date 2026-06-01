import requests

BASE = "http://localhost:5000/api"

for endpoint in ["/macro", "/market", "/fear-greed", "/news", "/chart/m2"]:
    try:
        res = requests.get(BASE + endpoint, timeout=20)
        data = res.json()
        status = data.get("status")
        if status == "ok":
            keys = list(data["data"].keys()) if isinstance(data["data"], dict) else f"{len(data['data'])}개 항목"
            print(f"OK  {endpoint}: {keys}")
        else:
            print(f"ERR {endpoint}: {data.get('message')}")
    except Exception as e:
        print(f"FAIL {endpoint}: {e}")
