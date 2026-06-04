from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from datetime import datetime, timedelta
from config import FRED_API_KEY, ANTHROPIC_API_KEY
import time

app = Flask(__name__)
CORS(app)

# 간단한 메모리 캐시
_cache = {}

CACHE_TTL = {
    "market": 30,      # 30초
    "fear_greed": 300, # 5분
    "macro": 300,
    "news": 300,
}

def cache_get(key):
    entry = _cache.get(key)
    ttl = CACHE_TTL.get(key, 300)
    if entry and time.time() - entry["ts"] < ttl:
        return entry["data"]
    return None

def cache_set(key, data):
    _cache[key] = {"data": data, "ts": time.time()}

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

def fred_get(series_id, limit=1, retries=3):
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit,
    }
    for attempt in range(retries):
        try:
            res = requests.get(FRED_BASE, params=params, timeout=20)
            data = res.json()
            obs = [o for o in data.get("observations", []) if o["value"] != "."]
            if obs:
                return obs
            # 값이 비어있으면 limit 늘려서 재시도 (최근 데이터가 "."일 수 있음)
            params["limit"] = limit + (attempt + 1) * 5
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(1)
    return []

def fred_history(series_id, days=365):
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "asc",
        "observation_start": start,
    }
    res = requests.get(FRED_BASE, params=params, timeout=20)
    data = res.json()
    return [o for o in data.get("observations", []) if o["value"] != "."]


@app.route("/api/macro")
def macro():
    """M2, 금리, RRP, Fed 대차대조표 최신값"""
    cached = cache_get("macro")
    if cached:
        return jsonify({"status": "ok", "data": cached})

    series_list = [
        ("m2",           "M2SL",      "십억달러"),
        ("fed_rate",     "FEDFUNDS",  "%"),
        ("rrp",          "RRPONTSYD", "십억달러"),
        ("fed_balance",  "WALCL",     "백만달러"),
        ("treasury_10y", "DGS10",     "%"),
        ("treasury_2y",  "DGS2",      "%"),
    ]
    result = {}
    for key, sid, unit in series_list:
        try:
            obs = fred_get(sid, 1)
            if obs:
                result[key] = {"value": float(obs[0]["value"]), "date": obs[0]["date"], "unit": unit}
        except Exception:
            pass

    # 실패한 항목 로그
    failed = [k for k, v in result.items() if v is None] if result else []
    if failed:
        print(f"[WARN] 누락된 FRED 시리즈: {failed}", flush=True)

    # 장단기 금리차 계산 (10년 - 2년)
    try:
        if "treasury_10y" in result and "treasury_2y" in result:
            spread = round(result["treasury_10y"]["value"] - result["treasury_2y"]["value"], 2)
            result["yield_spread"] = {"value": spread, "date": result["treasury_10y"]["date"], "unit": "%p"}
    except Exception:
        pass

    # 데이터 없는 항목은 null로 채워서 항상 반환
    all_keys = ["m2", "fed_rate", "rrp", "fed_balance", "treasury_10y", "treasury_2y", "yield_spread"]
    for k in all_keys:
        if k not in result:
            result[k] = None

    cache_set("macro", result)
    return jsonify({"status": "ok", "data": result})


@app.route("/api/market")
def market():
    """VIX, 코스피, 코스닥, S&P500, 나스닥, 원달러"""
    cached = cache_get("market")
    if cached:
        return jsonify({"status": "ok", "data": cached})
    try:
        import yfinance as yf
        tickers = {
            "vix":    "^VIX",
            "sp500":  "^GSPC",
            "nasdaq": "^IXIC",
            "kospi":  "^KS11",
            "kosdaq": "^KQ11",
            "usdkrw": "KRW=X",
            "dxy":    "DX-Y.NYB",
            "wti":    "CL=F",
            "gold":   "GC=F",
        }
        result = {}
        for key, symbol in tickers.items():
            try:
                t = yf.Ticker(symbol)
                hist = t.history(period="2d")
                if len(hist) >= 1:
                    latest = hist.iloc[-1]
                    prev   = hist.iloc[-2] if len(hist) >= 2 else hist.iloc[-1]
                    change_pct = ((latest["Close"] - prev["Close"]) / prev["Close"]) * 100
                    result[key] = {
                        "value": round(float(latest["Close"]), 2),
                        "change_pct": round(float(change_pct), 2),
                    }
            except:
                pass
        cache_set("market", result)
        return jsonify({"status": "ok", "data": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/fear-greed")
def fear_greed():
    """CNN 공포탐욕지수"""
    cached = cache_get("fear_greed")
    if cached:
        return jsonify({"status": "ok", "data": cached})
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.cnn.com/markets/fear-and-greed",
            "Accept": "application/json",
        }
        res = requests.get(url, headers=headers, timeout=20)
        data = res.json()
        fg = data["fear_and_greed"]
        result = {
            "score": round(fg["score"]),
            "rating": fg["rating"],
            "prev_close": round(fg.get("previous_close", 0)),
            "prev_week":  round(fg.get("previous_1_week", 0)),
            "prev_month": round(fg.get("previous_1_month", 0)),
        }
        cache_set("fear_greed", result)
        return jsonify({"status": "ok", "data": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/chart/<series>")
def chart(series):
    """FRED 시계열 차트 데이터"""
    series_map = {
        "m2":           "M2SL",
        "rrp":          "RRPONTSYD",
        "fed_balance":  "WALCL",
        "fed_rate":     "FEDFUNDS",
        "treasury_10y": "DGS10",
        "treasury_2y":  "DGS2",
    }
    if series not in series_map:
        return jsonify({"status": "error", "message": "unknown series"}), 400
    try:
        obs = fred_history(series_map[series], days=730)
        result = [{"date": o["date"], "value": float(o["value"])} for o in obs]
        return jsonify({"status": "ok", "data": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/news")
def news():
    """네이버 + Yahoo Finance + CNBC 뉴스 (영문은 한글 번역)"""
    cached = cache_get("news")
    if cached:
        return jsonify({"status": "ok", "data": cached})
    try:
        import xml.etree.ElementTree as ET
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source="en", target="ko")

        # 한국 뉴스 (이미 한글)
        kr_feeds = [
            ("연합뉴스", "https://www.yonhapnewstv.co.kr/category/news/economy/feed/"),
            ("동아일보", "https://rss.donga.com/economy.xml"),
        ]
        # 영문 뉴스 (번역 필요)
        en_feeds = [
            ("Yahoo Finance", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US"),
            ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664"),
        ]

        headers = {"User-Agent": "Mozilla/5.0"}
        items = []

        def clean_html(text):
            """HTML 태그 제거"""
            import re
            text = re.sub(r"<[^>]+>", "", text or "")
            text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'").replace("&quot;", '"')
            return text.strip()

        for source, feed_url in kr_feeds:
            try:
                res = requests.get(feed_url, headers=headers, timeout=20)
                root = ET.fromstring(res.content)
                for item in root.findall(".//item")[:6]:
                    title = item.findtext("title", "").strip()
                    link  = item.findtext("link", "").strip()
                    pub   = item.findtext("pubDate", "")
                    desc  = clean_html(item.findtext("description", ""))[:400]
                    if title:
                        items.append({"title": title, "summary": desc, "link": link, "date": pub, "source": source})
            except:
                pass

        for source, feed_url in en_feeds:
            try:
                res = requests.get(feed_url, headers=headers, timeout=20)
                root = ET.fromstring(res.content)
                for item in root.findall(".//item")[:5]:
                    title = item.findtext("title", "").strip()
                    link  = item.findtext("link", "").strip()
                    pub   = item.findtext("pubDate", "")
                    desc  = clean_html(item.findtext("description", ""))[:400]
                    if title:
                        try:
                            title_ko = translator.translate(title)
                            desc_ko  = translator.translate(desc) if desc else ""
                        except:
                            title_ko = title
                            desc_ko  = desc
                        items.append({"title": title_ko, "title_en": title, "summary": desc_ko, "link": link, "date": pub, "source": source})
            except:
                pass

        cache_set("news", items[:25])
        return jsonify({"status": "ok", "data": items[:25]})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    """Claude AI 주식 질문 답변"""
    try:
        data = request.get_json()
        message = data.get("message", "").strip()
        if not message:
            return jsonify({"status": "error", "message": "질문이 없습니다."}), 400

        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5",
                "max_tokens": 1024,
                "system": (
                    "당신은 주식, 매크로 경제, 투자 전략 전문가입니다. "
                    "CM 주식연구소의 AI 어시스턴트로서 사용자의 투자 관련 질문에 "
                    "명확하고 간결하게 한국어로 답변합니다. "
                    "투자 결정은 본인 책임임을 항상 인지시켜 주세요."
                ),
                "messages": [{"role": "user", "content": message}],
            },
            timeout=30,
        )
        result = res.json()
        answer = result["content"][0]["text"]
        return jsonify({"status": "ok", "answer": answer})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



if __name__ == "__main__":
    app.run(debug=True, port=5000)
