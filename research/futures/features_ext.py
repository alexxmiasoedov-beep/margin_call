"""Признаки с других бирж и источников на момент входа (только прошлое) → features_ext.csv.
Gate: ликвидации, OI, LSR, топ-трейдеры, число лонгистов/шортистов (5 мин). Binance спот: объёмы, тейкеры, базис.
Binance стакан (bookDepth): глубина ±1/2/5%. Upbit: объём в KRW, кимчи-премия."""
import json, os, time, subprocess, datetime, io, zipfile, threading
import numpy as np, pandas as pd
from concurrent.futures import ThreadPoolExecutor
import bv
from sim import SIG
UTC = datetime.timezone.utc
day = lambda t: datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d")
os.makedirs("cache_ext", exist_ok=True)
def jget(url, key, tries=5):
    fn = os.path.join("cache_ext", key)
    if os.path.exists(fn): return json.load(open(fn))
    for i in range(tries):
        r = subprocess.run(["curl", "-sS", "-m", "30", url], capture_output=True, text=True)
        try:
            j = json.loads(r.stdout)
            if isinstance(j, dict) and ("error" in j or "label" in j) and "too_many" in r.stdout.lower(): raise ValueError
            json.dump(j, open(fn, "w")); return j
        except Exception:
            time.sleep(1 + i * 2)
    return None
UPB = {m["market"] for m in (jget("https://api.upbit.com/v1/market/all", "upbit_markets.json") or [])}
upl = threading.Semaphore(4)

def gate(s, f):
    te = s["te"]; j = jget(f"https://api.gateio.ws/api/v4/futures/usdt/contract_stats?contract={s['sym']}_USDT&from={te - 86400 - 600}&interval=5m&limit=300",
                           f"gate_{s['sym']}_{te}.json")
    if not isinstance(j, list) or not j: return
    d = pd.DataFrame(j); d = d[d.time <= te - 300]
    if len(d) < 50: return
    now = d.iloc[-1]
    def ago(T):
        x = d[d.time <= te - 300 - T]; return x.iloc[-1] if len(x) else None
    oi = now.open_interest_usd; f["g_oi_musd"] = oi / 1e6
    for lab, T in (("1h", 3600), ("4h", 14400), ("24h", 86000)):
        a = ago(T)
        if a is not None:
            f[f"g_oi_ch_{lab}"] = (oi / a.open_interest_usd - 1) * 100 if a.open_interest_usd else np.nan
            f[f"g_lsracc_ch_{lab}"] = now.lsr_account / a.lsr_account - 1 if a.lsr_account else np.nan
            f[f"g_users_ch_{lab}"] = (now.long_users / max(now.short_users, 1)) / (a.long_users / max(a.short_users, 1)) - 1 if a.long_users else np.nan
        w = d[d.time > te - 300 - T]
        f[f"g_liq_short_{lab}"] = w.short_liq_usd.sum() / oi * 100 if oi else np.nan     # ликвидации шортов, % от OI
        f[f"g_liq_long_{lab}"] = w.long_liq_usd.sum() / oi * 100 if oi else np.nan
        lt, st = w.long_taker_size.sum(), w.short_taker_size.sum(); f[f"g_taker_long_share_{lab}"] = lt / (lt + st) if lt + st else np.nan
    f["g_lsr_acc"] = now.lsr_account; f["g_top_lsr_size"] = now.top_lsr_size; f["g_top_lsr_acc"] = now.top_lsr_account
    f["g_users_ratio"] = now.long_users / max(now.short_users, 1)

def spot(s, f):
    te = s["te"]; A = bv.kfull_spot(s["sym"], [day(te - 86400), day(te)])
    if A is None: f["spot_listed"] = 0; return
    A = A[A[:, 0] < te]
    if len(A) < 600: f["spot_listed"] = 0; return
    f["spot_listed"] = 1
    t, o, h, l, c, v, q, n, b = A.T
    sp = c[-1]; f["basis"] = (s["entry"] / sp - 1) * 100
    w24 = t >= te - 86400; q24 = q[w24].sum(); f["spot_qv24_musd"] = q24 / 1e6
    for lab, T in (("1h", 3600), ("4h", 14400)):
        w = t >= te - T; f[f"spot_vrel_{lab}"] = (q[w].sum() / T) / (q24 / 86400) if q24 else np.nan
        f[f"spot_tbuy_{lab}"] = b[w].sum() / q[w].sum() if q[w].sum() else np.nan
        k = np.searchsorted(t, te - T - 60, "right") - 1
        f[f"spot_ch_{lab}"] = (sp / c[k] - 1) * 100 if k >= 0 else np.nan
    f["spot_q4h_musd"] = q[t >= te - 14400].sum() / 1e6

def depth(s, f):
    te = s["te"]; rows = []
    for d in (day(te - 86400), day(te)):
        data = bv.fetch(f"daily/bookDepth/{s['sym']}USDT/{s['sym']}USDT-bookDepth-{d}.zip")
        if not data: continue
        z = zipfile.ZipFile(io.BytesIO(data))
        for ln in z.read(z.namelist()[0]).decode().splitlines()[1:]:
            p = ln.split(",")
            try: rows.append((int(datetime.datetime.strptime(p[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp()), float(p[1]), float(p[3])))
            except (ValueError, IndexError): pass
    if not rows: return
    d = pd.DataFrame(rows, columns=["t", "pct", "notional"]); d = d[d.t < te]
    if not len(d): return
    def snap(T):
        x = d[d.t <= T]
        if not len(x): return None
        tt = x.t.max();
        return None if T - tt > 600 else x[x.t == tt].set_index("pct").notional
    a = snap(te); b = snap(te - 3600)
    if a is None: return
    for k in (1.0, 2.0, 5.0):
        bid, ask = a.get(-k, np.nan), a.get(k, np.nan)
        f[f"book_imb_{k:g}"] = (bid - ask) / (bid + ask)                    # >0 — покупателей в стакане больше
        f[f"book_ask_{k:g}_kusd"] = ask / 1e3
        if b is not None:
            b_bid, b_ask = b.get(-k, np.nan), b.get(k, np.nan); f[f"book_imb_ch1h_{k:g}"] = f[f"book_imb_{k:g}"] - (b_bid - b_ask) / (b_bid + b_ask)
            f[f"book_depth_ch1h_{k:g}"] = (bid + ask) / (b_bid + b_ask) - 1

def upbit(s, f):
    m = f"KRW-{s['sym']}"; f["upbit_listed"] = int(m in UPB)
    if m not in UPB: return
    te = s["te"]; to = datetime.datetime.fromtimestamp(te, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with upl:
        c = jget(f"https://api.upbit.com/v1/candles/minutes/15?market={m}&to={to}&count=96", f"upb_{m}_{te}.json")
        u = jget(f"https://api.upbit.com/v1/candles/minutes/15?market=KRW-USDT&to={to}&count=1", f"upb_USDT_{te}.json")
    if not isinstance(c, list) or not c or not isinstance(u, list) or not u: return
    c = sorted(c, key=lambda x: x["timestamp"]); usd = u[0]["trade_price"]
    px = c[-1]["trade_price"] / usd; f["kimchi"] = (px / s["entry"] - 1) * 100
    vol = np.array([x["candle_acc_trade_price"] for x in c]) / usd
    f["upbit_qv24_musd"] = vol.sum() / 1e6; f["upbit_vrel_1h"] = vol[-4:].sum() / (vol.sum() / 24) if vol.sum() else np.nan
    f["upbit_ch_4h"] = (c[-1]["trade_price"] / c[-17]["trade_price"] - 1) * 100 if len(c) > 17 else np.nan

def job(s):
    f = {"sym": s["sym"], "ep": s["ep"]}
    for fn in (gate, spot, depth, upbit):
        try: fn(s, f)
        except Exception as e: print("ошибка", fn.__name__, s["sym"], s["ep"], repr(e), flush=True)
    return f
with ThreadPoolExecutor(8) as ex:
    out = list(ex.map(job, SIG))
pd.DataFrame(out).to_csv("features_ext.csv", index=False); print("готово", len(out))
