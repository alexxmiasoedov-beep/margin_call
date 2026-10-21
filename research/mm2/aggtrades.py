"""Лента сделок (aggTrades фьючерса) перед моментами памп/дамп/покой: крупные агрессивные ордера, «проглатывание» уровней,
мелкие (розница) против крупных (киты). Ордер тейкера = подряд идущие сделки с одной миллисекундой и стороной.
Окна: последний час до t0 против базы [t0−6 ч, t0−1 ч). Файлы дня качаются, обрабатываются и удаляются."""
import pickle, datetime, os, io, zipfile, subprocess, multiprocessing as mp, time
import numpy as np, pandas as pd
UTC = datetime.timezone.utc
K = pickle.load(open("kaia/k15_all.pkl", "rb"))
MOM = pickle.load(open(os.environ.get("MOM", "mm2/moments.pkl"), "rb"))
OUT = os.environ.get("OUT", "mm2/agg_feats.pkl"); TMP = "/tmp/claude-0/-home-user-romanovdecor-site/55ef3fa1-b1d3-5bfb-a9b4-6937479954ec/scratchpad/dl"
day = lambda t: datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d")
def load(sym, d, wins=()):
    fn = f"{TMP}/{sym}_{d}.zip"; url = f"https://data.binance.vision/data/futures/um/daily/aggTrades/{sym}USDT/{sym}USDT-aggTrades-{d}.zip"
    for i in range(4):
        r = subprocess.run(["curl", "-sS", "-m", "300", "-w", "%{http_code}", "-o", fn, url], capture_output=True, text=True)
        if r.stdout == "200": break
        if r.stdout == "404": return None
        time.sleep(3 + 3 * i)
    else: return None
    out = []
    try:
        z = zipfile.ZipFile(fn)
        for df in pd.read_csv(z.open(z.namelist()[0]), usecols=[1, 2, 5, 6], header=0, names=["p", "q", "t", "m"],
                              dtype={"p": float, "q": float, "t": np.int64}, chunksize=2_000_000):
            keep = np.zeros(len(df), bool); tv = df.t.values
            for a, b in wins: keep |= (tv >= a * 1000) & (tv < b * 1000)
            if keep.any(): out.append(df[keep])
    except Exception: out = []
    os.remove(fn); return pd.concat(out, ignore_index=True) if out else None
def orders(df):
    t = df.t.values; m = (df.m.astype(str).str.lower() == "true").values; p = df.p.values; v = p * df.q.values
    new = np.r_[True, (t[1:] != t[:-1]) | (m[1:] != m[:-1])]; st = np.flatnonzero(new)
    notional = np.add.reduceat(v, st); lv = np.add.reduceat(np.r_[True, p[1:] != p[:-1]] & ~new | new, st)
    imp = np.abs(p[np.r_[st[1:] - 1, len(p) - 1]] / p[st] - 1)
    return t[st] / 1000.0, ~m[st], notional, lv, imp                 # время, покупка?, $ ордера, уровней, сдвиг цены
def feats(O, t0):
    tt, buy, nv, lv, imp = O
    w1 = (tt >= t0 - 3600) & (tt < t0); w0 = (tt >= t0 - 6 * 3600) & (tt < t0 - 3600); w10 = (tt >= t0 - 600) & (tt < t0)
    if w1.sum() < 30 or w0.sum() < 150: return {}
    thr = np.percentile(nv[w0], 99); small = np.percentile(nv[w0], 50)
    tot1 = nv[w1].sum(); r = {}
    bb, bs = (nv[w1 & buy & (nv >= thr)]).sum(), (nv[w1 & ~buy & (nv >= thr)]).sum()
    r["a_big_buy"] = bb / tot1; r["a_big_sell"] = bs / tot1; r["a_big_net"] = (bb - bs) / tot1
    r["a_big_rate"] = (w1 & (nv >= thr)).sum() / max((w0 & (nv >= thr)).sum() / 5, 1)
    sm = w1 & (nv <= small); r["a_small_net"] = (nv[sm & buy].sum() - nv[sm & ~buy].sum()) / max(nv[sm].sum(), 1e-9)
    r["a_whale_vs_retail"] = r["a_big_net"] - r["a_small_net"]
    sw1b, sw1s = (w1 & buy & (lv >= 3)).sum(), (w1 & ~buy & (lv >= 3)).sum(); sw0 = (w0 & (lv >= 3)).sum() / 5
    r["a_sweep_net"] = (sw1b - sw1s) / max(sw1b + sw1s, 1); r["a_sweep_rate"] = (sw1b + sw1s) / max(sw0, 1)
    r["a_imp_buy"] = imp[w1 & buy].sum() / max(imp[w1].sum(), 1e-12)        # доля сдвига цены, сделанная покупателями
    r["a_ord_size"] = nv[w1].mean() / nv[w0].mean(); r["a_rate"] = w1.sum() / (w0.sum() / 5)
    r["a_cnt_buy"] = (w1 & buy).sum() / w1.sum(); r["a_vol_buy"] = nv[w1 & buy].sum() / tot1
    r["a_cnt_vs_vol"] = r["a_cnt_buy"] - r["a_vol_buy"]                     # много мелких покупок при продаже объёмом и т.п.
    if w10.sum() >= 10:
        r["a_rate10"] = w10.sum() / (w0.sum() / 30); r["a_net10"] = (nv[w10 & buy].sum() - nv[w10 & ~buy].sum()) / max(nv[w10].sum(), 1e-9)
    w15 = (tt >= t0 - 900) & (tt < t0)
    if w15.sum() >= 20:
        tot15 = nv[w15].sum(); bb15 = nv[w15 & buy & (nv >= thr)].sum(); bs15 = nv[w15 & ~buy & (nv >= thr)].sum(); sm15 = w15 & (nv <= small)
        r["a15_big_net"] = (bb15 - bs15) / tot15; r["a15_small_net"] = (nv[sm15 & buy].sum() - nv[sm15 & ~buy].sum()) / max(nv[sm15].sum(), 1e-9)
        r["a15_whale_vs_retail"] = r["a15_big_net"] - r["a15_small_net"]; r["a15_imp_buy"] = imp[w15 & buy].sum() / max(imp[w15].sum(), 1e-12)
        r["a15_big_share"] = (bb15 + bs15) / tot15; r["a15_ord_size"] = nv[w15].mean() / nv[w0].mean()
        b15, s15 = (w15 & buy & (lv >= 3)).sum(), (w15 & ~buy & (lv >= 3)).sum(); r["a15_sweep_net"] = (b15 - s15) / max(b15 + s15, 1)
        r["a15_cnt_vs_vol"] = (w15 & buy).sum() / w15.sum() - nv[w15 & buy].sum() / tot15
    r["a_max_buy"] = nv[w1 & buy].max() / tot1 if (w1 & buy).any() else 0; r["a_max_sell"] = nv[w1 & ~buy].max() / tot1 if (w1 & ~buy).any() else 0
    return r
BY = {}
for x in MOM: BY.setdefault(x[1], []).append(x)
def coin(s):
    ms = BY[s]; t0s = [K[s][i, 0] + 900 for _, _, i in ms]
    days = sorted({day(t) for t0 in t0s for t in (t0 - 6 * 3600, t0 - 1)})
    wins = [(t0 - 6 * 3600, t0) for t0 in t0s]
    parts = [df for df in (load(s, d, wins) for d in days) if df is not None]
    if not parts: return [dict(g=g, s=s, i=i) for g, _, i in ms]
    df = pd.concat(parts, ignore_index=True)
    lo = min(t0s) - 6 * 3600; hi = max(t0s); df = df[(df.t >= lo * 1000) & (df.t < hi * 1000)].sort_values("t", kind="stable")
    O = orders(df) if len(df) else None; out = []
    for (g, _, i), t0 in zip(ms, t0s):
        r = dict(g=g, s=s, i=i, t0=t0)
        if O is not None: r.update(feats(O, t0))
        out.append(r)
    return out
if __name__ == "__main__":
    os.makedirs(TMP, exist_ok=True); import warnings; warnings.filterwarnings("ignore")
    res = []
    with mp.get_context("fork").Pool(5) as pool:
        for n, rows in enumerate(pool.imap_unordered(coin, sorted(BY, key=lambda s: -len(BY[s])), chunksize=1)):
            res += rows
            if n % 20 == 0: print(datetime.datetime.now().strftime("%H:%M:%S"), "монет", n, flush=True)
    pickle.dump(res, open(OUT, "wb")); print("готово", len(res), "с признаками", sum(1 for r in res if "a_big_net" in r), flush=True)
