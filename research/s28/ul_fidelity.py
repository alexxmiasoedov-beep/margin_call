"""Сверка журнала 🔓 в боте с бэктестом s28 (правило «cliff ≥ 5% или ≥ 25%», шорт T − 7 → T + 1 сут, стоп +50%).
Правило бота scanner.unlock_rule вызывается по дням 01.10.2024–10.10.2026:
- в 00:00 UTC — список монет: s28/unlock_listing.json, монеты в обращении и цена — история CMC (s28/hist) на этот момент;
- потом проходы раз в минуту до конца очереди, дальше раз в 15 мин до следующих суток;
- расписание — прошлые события CMC (s28/ev) позже «сейчас», по 100 на страницу;
- список контрактов Binance — фьючерсы со свечами с объёмом в этот момент (s2/k2y.pkl), цена — закрытие 15-мин свечи.
Сравниваются входы (монета, срок) с 239 сделками бэктеста (s28/robust.pkl); для входов бота — доход по той же методике
(common.trade: вход в закрытии 15-мин свечи, комиссия 0,1%, фактический фандинг, стоп с проскальзыванием 0,2%).
Запуск из папки с данными: python3 ul_fidelity.py"""
import bisect
import json
import os
import sys
import tempfile
import time
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["STATE_FILE"] = os.path.join(tempfile.mkdtemp(), "state.json"); os.environ["POSITION_USDT"] = "1"
from unlock_study import CUT, DAY, K, ct, hist, live, ts, tokens       # noqa: E402
from unlock_trades import run as bt_run                               # noqa: E402

sys.path.insert(0, os.path.join(HERE, "..", "..", "bot"))
import scanner, trader                                                # noqa: E402

D0, D1 = 1727740800, 1791590400            # 01.10.2024 … 10.10.2026 (архив свечей — по 18.10.2026)
CLOCK = [float(D0)]
time.time = lambda: CLOCK[0]
LOG = []
scanner.log = lambda *a: LOG.append((CLOCK[0], " ".join(str(x) for x in a)))
TOK = tokens()
L = {r["cryptoId"]: r for r in json.load(open("s28/unlock_listing.json"))}
EV, HS = {}, {}
for cid, sym, fut in TOK:
    p = f"s28/ev/{cid}_past.json"
    ev = sorted(json.load(open(p)), key=lambda e: e["time"]) if os.path.exists(p) else []
    EV[cid] = ([ts(e["time"]) for e in ev], ev)
    h = hist(cid)
    HS[cid] = (h.t.values, h.px.values, h.circ.values) if h is not None else None
LIVE = {s: live(s) for s in K}
OPEN, ENTRIES = {}, []


def at(cid, t):
    h = HS.get(cid)
    if h is None:
        return 0.0, 0.0
    i = np.searchsorted(h[0], t, "right") - 1
    if i < 0:
        return 0.0, 0.0
    return float(h[2][i] or 0), float(h[1][i] or 0)


def fake_http_json(url, timeout=30):
    if "/token-unlock/listing" in url:
        page = int(url.split("start=")[1].split("&")[0])
        rows = []
        for cid, sym, fut in TOK[(page - 1) * 100: page * 100]:
            circ, px = at(cid, CLOCK[0])
            rows.append({"cryptoId": cid, "symbol": sym, "circulatingSupply": circ, "quotes": [{"price": px}]})
        return {"data": {"tokenUnlockList": rows, "totalCount": str(len(TOK))}}
    if "/token-unlock/event" in url:
        cid = int(url.split("cryptoId=")[1].split("&")[0]); page = int(url.split("page=")[1].split("&")[0])
        tt, ev = EV.get(cid, ([], []))
        k = bisect.bisect_right(tt, CLOCK[0]) + (page - 1) * 100
        return {"data": {"cryptoId": cid, "tokenEvent": ev[k:k + 100]}}
    raise AssertionError(url)


def fake_request(method, path, params=None, signed=True, **kw):
    params = params or {}
    if path == "/fapi/v1/exchangeInfo":
        return {"symbols": [{"symbol": f"{s}USDT", "contractType": "PERPETUAL", "status": "TRADING", "quoteAsset": "USDT",
                             "onboardDate": int(lo * 1000), "filters": []}
                            for s, (lo, hi) in LIVE.items() if lo <= CLOCK[0] <= hi]}
    if path == "/fapi/v1/premiumIndex":
        s = params["symbol"][:-4]; a = K[s]; i = int(np.searchsorted(a["t"], CLOCK[0], "right")) - 1
        return {"markPrice": str(float(a["c"][i]))} if i >= 0 else {}
    raise AssertionError(path)


def fake_open(state, key, sym, rule, note, price=None, hold_h=None):
    OPEN[sym] = CLOCK[0] + hold_h * 3600
    ENTRIES.append(dict(s=sym, t_in=CLOCK[0], hold_h=hold_h, T=CLOCK[0] + hold_h * 3600 - DAY))
    return f"🔓 {sym}"


scanner.http_json = fake_http_json
trader._request = fake_request
trader.virt_open = fake_open
scanner._virt_is_open = lambda state, key, sym: OPEN.get(sym, 0) > CLOCK[0]

if __name__ == "__main__":
    state = {}
    t_start = time.perf_counter() if hasattr(time, "perf_counter") else 0
    for D in range(D0, D1, 86400):
        CLOCK[0] = float(D)
        scanner.unlock_rule(state)
        for _ in range(60):                                   # очередь — по 15 монет за проход раз в минуту
            if "queue" not in state.get("ul", {}):
                break
            CLOCK[0] += 60
            scanner.unlock_rule(state)
        while CLOCK[0] + 900 < D + 86400:
            CLOCK[0] += 900
            scanner.unlock_rule(state)
        if D % (30 * 86400) < 86400:
            print(f"  {pd.Timestamp(D, unit='s'):%Y-%m-%d}: входов {len(ENTRIES)}", flush=True)
    B = pd.DataFrame(ENTRIES)
    B.to_pickle("s28/ul_fidelity.pkl")
    R = pd.read_pickle("s28/robust.pkl"); R = R[R.sl == 0.5]
    R = R[(R.cliff & (R["size"] >= 5)) | (R["size"] >= 25)]
    R = R[R.t - 7 * DAY >= D0]
    print(f"\nвходов бота {len(B)}, сделок бэктеста {len(R)}")
    used, miss = set(), []
    for r in R.itertuples():
        m = B[(B.s == r.s) & ((B["T"] - r.t).abs() <= 2 * DAY)]
        if len(m):
            used.add(m.index[0])
        else:
            miss.append(r)
    print(f"совпало (та же монета, разлок ±2 сут): {len(R) - len(miss)} из {len(R)}; лишних у бота: {len(B) - len(used)}")
    lag = [(B.loc[i, "T"] - R[(R.s == B.loc[i, "s"]) & ((R.t - B.loc[i, "T"]).abs() <= 2 * DAY)].t.iloc[0]) / 3600 for i in used]
    print(f"сдвиг даты разлока у совпавших, ч: 0 — {np.mean(np.abs(lag) < 1):.0%}, медиана |сдвига| {np.median(np.abs(lag)):.1f}")
    for r in miss[:25]:
        why = [x for c, x in LOG if r.s in x and abs(c - (r.t - 7 * DAY)) < 3 * DAY]
        print(f"  нет у бота: {r.s} {pd.Timestamp(r.t, unit='s'):%Y-%m-%d} {r.size:.1f}% — {why[-1][:150] if why else 'нет строк'}")
    for i in [i for i in B.index if i not in used][:25]:
        b = B.loc[i]
        print(f"  лишний у бота: {b.s} разлок {pd.Timestamp(b['T'], unit='s'):%Y-%m-%d %H:%M}")
    rows = []
    for b in B.itertuples():
        x = bt_run(b.s, b.t_in, b.hold_h / 24, 0.5)
        if x:
            rows.append(dict(s=b.s, t=b.T, **x))
    X = pd.DataFrame(rows)
    m, t, n = ct(X.net.values, X.t.values)
    print(f"\nдоход входов бота (та же методика): n={n} {m*100:+.2f}% на сделку (t {t:+.1f}), медиана {X.net.median()*100:+.1f}%, "
          f"в плюсе {(X.net > 0).mean():.0%}, половины {X[X.t < CUT].net.mean()*100:+.2f} / {X[X.t >= CUT].net.mean()*100:+.2f}%")
    m, t, n = ct(R.net.values, R.t.values)
    print(f"бэктест: n={n} {m*100:+.2f}% (t {t:+.1f})")
