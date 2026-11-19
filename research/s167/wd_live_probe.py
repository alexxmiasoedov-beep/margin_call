"""s167 — живой прогон правила 🐋 из облака: настоящие CoinMarketCap, CoinGecko и узлы Ethereum; фьючерсный API Binance из
облака закрыт, поэтому список контрактов и цены фьючерсов подменяются ценами спота Binance (data-api.binance.vision) и списком
фьючерсов из архива s2/k2y.pkl. Проходы раз в «2 мин» по часам теста; печатает строки «ЗАВОДЫ». Запуск из /home/user/mc_data:
python3 <repo>/research/s167/wd_live_probe.py [проходов]"""
import json
import os
import pickle
import sys
import tempfile
import time
import urllib.request

os.environ["STATE_FILE"] = os.path.join(tempfile.mkdtemp(), "state.json")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bot"))
import scanner, trader  # noqa: E402

LOG = []
scanner.log = lambda *a: (LOG.append(" ".join(str(x) for x in a)), print(" ".join(str(x) for x in a)[:300], flush=True))
spot = {x["symbol"]: float(x["price"]) for x in json.loads(urllib.request.urlopen(urllib.request.Request(
    "https://data-api.binance.vision/api/v3/ticker/price", headers={"User-Agent": "research-script/1.0"}), timeout=60).read())}
perps = [s for s in pickle.load(open("s2/k2y.pkl", "rb"))]
px = {}
for fs in perps:
    coin, mult = scanner._wd_base(fs)
    if coin + "USDT" in spot:
        px[fs + "USDT"] = spot[coin + "USDT"] * mult
trader._contracts.update({s: {"onboard": 0} for s in px})
real_http_json = scanner.http_json


def http_json(url, timeout=30):
    if url == "https://fapi.binance.com/fapi/v1/ticker/price":
        return [{"symbol": s, "price": str(p)} for s, p in px.items()]
    return real_http_json(url, timeout)


scanner.http_json = http_json
state = {}
CLOCK = [time.time()]
scanner.time.time = lambda: CLOCK[0]
n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
back = "back" in sys.argv[2:]                       # после загрузки decimals — один опрос за последние WD_BACK блоков
for i in range(n):
    w = state.get("wd", {})
    if back and w.get("block") and len(w.get("dec") or {}) >= len(w.get("tok") or {}) > 0:
        w["block"] -= scanner.WD_BACK - 1; back = False
        print(f"опрос назад на {scanner.WD_BACK} блоков (~4 ч)", flush=True)
    m = scanner.whale_deposit_rule(state)
    w = state.get("wd", {})
    print(f"проход {i + 1}: токенов {len(w.get('tok') or {})}, decimals {len(w.get('dec') or {})}, блок {w.get('block')}, "
          f"ждут входа {sorted(w.get('pend') or {})}, сообщений {len(m)}", flush=True)
    CLOCK[0] += scanner.WD_EVERY
    time.sleep(1)
