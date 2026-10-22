"""История ставок маржи Binance (публичный bapi vip/spec/history-interest-rate, без ключа): окна по 31 сутки
с 01.09.2024. Активы: текущий список маржи (490) + монеты фьючерсов и канала MarginData (для делистингованных из маржи —
пробы раз в 3 месяца, при находке — вся история). По файлу на актив: s11/rates/<АКТИВ>.csv (время, дневная ставка)."""
import json, subprocess, time, datetime, os, pickle, re, sys
from concurrent.futures import ThreadPoolExecutor
B = "https://www.binance.com/bapi/margin/v1/public/margin/vip/spec/history-interest-rate"
D = 86400; W = 31 * D
START = datetime.datetime(2024, 9, 1, tzinfo=datetime.timezone.utc).timestamp(); NOW = time.time()
def q(asset, a, b):
    u = f"{B}?asset={asset}&vipLevel=0&startTime={int(a * 1000)}&endTime={int(b * 1000)}"
    for k in range(5):
        r = subprocess.run(["curl", "-sS", "-m", "30", u], capture_output=True, text=True).stdout
        try:
            j = json.loads(r)
        except Exception:
            time.sleep(3 + 5 * k); continue
        if j.get("success") and isinstance(j.get("data"), list):
            return {int(x["timestamp"]) // 1000: float(x["dailyInterestRate"]) for x in j["data"]}
        if j.get("code") in ("051026", "000002"):          # параметр не подходит (актива нет и т. п.)
            return {}
        time.sleep(3 + 5 * k)
    return None
def windows():
    b = NOW
    while b > START:
        yield max(START, b - W + 1), b
        b -= W
def full(asset, early_stop=True):
    res, empty, err = {}, 0, 0
    for a, b in windows():
        r = q(asset, a, b)
        if r is None:
            err += 1; continue
        res.update(r)
        empty = 0 if r else empty + 1
        if early_stop and empty >= 3:
            break
    return res, err
def probe(asset):
    for y, m in ((2024, 10), (2025, 1), (2025, 4), (2025, 7), (2025, 10), (2026, 1), (2026, 4), (2026, 7)):
        a = datetime.datetime(y, m, 1, tzinfo=datetime.timezone.utc).timestamp()
        r = q(asset, a, a + W - 1)
        if r:
            return True
    return False
def job(item):
    asset, current = item
    fn = f"s11/rates/{asset}.csv"
    if os.path.exists(fn):
        return asset, "есть", 0
    if not current and not probe(asset):
        open(fn, "w").close(); return asset, "нет истории", 0
    res, err = full(asset, early_stop=current)
    with open(fn, "w") as f:
        for t in sorted(res):
            f.write(f"{t},{res[t]}\n")
    return asset, len(res), err
spec = json.loads(subprocess.run(["curl", "-sS", "-m", "30", "https://www.binance.com/bapi/margin/v1/public/margin/vip/spec/list-all"],
                                 capture_output=True, text=True).stdout)
cur = [a["assetName"] for a in spec["data"]]
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
K = pickle.load(open("s2/k2y.pkl", "rb")); G = pickle.load(open("s7/margin.pkl", "rb"))["G"]
extra = sorted(({strip(s) for s in K} | set(G)) - set(cur))
extra = [a for a in extra if re.fullmatch(r"[A-Z0-9]{2,15}", a)]
items = [(a, True) for a in cur] + [(a, False) for a in extra]
print("текущих", len(cur), "дополнительных", len(extra), flush=True)
t0 = time.time(); done = 0
with ThreadPoolExecutor(6) as ex:
    for asset, n, err in ex.map(job, items):
        done += 1
        if done % 50 == 0 or err:
            print(f"{time.time() - t0:.0f} с: {done}/{len(items)} {asset} {n} ошибок окон {err}", flush=True)
print("готово", time.time() - t0, flush=True)
