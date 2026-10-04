"""Признаки на момент входа для каждого сигнала (только прошлое) + исходы сделки → features.csv."""
import json, re, datetime, pickle
import numpy as np, pandas as pd
from concurrent.futures import ThreadPoolExecutor
import bv
from sim import SIG, trade, fh_entry, FUND
UTC = datetime.timezone.utc
MONTHS = [f"2026-{m:02d}" for m in range(2, 10)]
day = lambda t: datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d")
num = lambda s: float(s[:-1]) * {"K": 1e3, "M": 1e6, "B": 1e9}[s[-1]] if s[-1] in "KMB" else float(s)

# строки канала для сигналов: BOR, REP, B/R, CHNG, число монет в посте, место в посте
want = {(s["sym"], s["ep"]) for s in SIG}; eps = {s["ep"] for s in SIG}; CH = {}; RUN = {}
hist = {}
for ln in open("posts.jsonl"):
    pid, ts, txt = json.loads(ln); ep = int(datetime.datetime.fromisoformat(ts).timestamp())
    lines = [m for m in (re.match(r'^([A-Z0-9]+)\s+([\d.]+[KMB]?)\s+([\d.]+[KMB]?)\s+([\d.]+)\s+(-?[\d.]+)\s*$', x.strip()) for x in txt.splitlines()) if m]
    for pos, m in enumerate(lines):
        hist.setdefault(m.group(1), []).append((ep, num(m.group(2)), num(m.group(3)), float(m.group(4)), float(m.group(5))))
        if (m.group(1), ep) in want:
            CH[(m.group(1), ep)] = dict(ch_bor=num(m.group(2)), ch_rep=num(m.group(3)), ch_br=float(m.group(4)), ch_chng=float(m.group(5)),
                                        ch_ncoins=len(lines), ch_pos=pos)
for (sym, ep), d in CH.items():
    h = [x for x in hist[sym] if x[0] <= ep]; h.sort()
    run0 = ep; k = len(h) - 1
    while k > 0 and h[k][0] - h[k - 1][0] <= 1800: k -= 1
    run0 = h[k][0]; run = [x for x in h if x[0] >= run0]
    d["ch_run_h"] = (ep - run0) / 3600; d["ch_run_posts"] = len(run)
    d["ch_bor_vs_start"] = d["ch_bor"] / run[0][1] if run[0][1] else np.nan          # рост займа за серию
    prev = [x for x in h if ep - 7 * 86400 <= x[0] < run0]
    d["ch_posts_7d_before"] = len(prev)                                                 # как часто монета была в канале за неделю до серии
    d["ch_bor_vs_7d"] = d["ch_bor"] / np.median([x[1] for x in prev]) if prev else np.nan

BTC = bv.kfull("BTC", "klines", "15m", MONTHS)

def rsi(c, n=14):
    d = np.diff(c[-(n * 4):]); up = np.where(d > 0, d, 0); dn = np.where(d < 0, -d, 0)
    a, b = up[:n].mean(), dn[:n].mean()
    for u, w in zip(up[n:], dn[n:]): a = (a * (n - 1) + u) / n; b = (b * (n - 1) + w) / n
    return 100 - 100 / (1 + a / b) if b > 0 else 100.0

def feats(s):
    sym, te, p = s["sym"], s["te"], s["entry"]; f = {}
    K = bv.kfull(sym, "klines", "15m", MONTHS)
    A = bv.kfull(sym, "klines", "1m", (), [day(te - 2 * 86400), day(te - 86400), day(te)])
    M = bv.metrics(sym, [day(te - 2 * 86400), day(te - 86400), day(te)])
    P = bv.kfull(sym, "premiumIndexKlines", "5m", MONTHS)
    if A is None or K is None: return None
    A = A[A[:, 0] < te]; K = K[K[:, 0] + 900 <= te]
    t1, o1, h1, l1, c1, v1, q1, n1, b1 = A.T
    def px(T):                                   # цена в момент T = close минуты, закрывшейся к T
        k = np.searchsorted(t1, T - 60, "right") - 1
        return c1[k] if k >= 0 and T - t1[k] < 3 * 3600 else np.nan
    def win(T):                                  # маска минут в окне [te − T, te)
        return t1 >= te - T
    for lab, T in (("1m", 60), ("5m", 300), ("15m", 900), ("30m", 1800), ("1h", 3600), ("2h", 7200), ("4h", 14400), ("6h", 21600), ("12h", 43200), ("24h", 86400)):
        f[f"ch_{lab}"] = (p / px(te - T) - 1) * 100
    tK, oK, hK, lK, cK, vK, qK, nK, bK = K.T
    for lab, n in (("48h", 192), ("72h", 288), ("7d", 672)):
        f[f"ch_{lab}"] = (p / cK[-n] - 1) * 100 if len(cK) > n else np.nan
    f["ch_4h_before_24h"] = (px(te - 14400) / px(te - 86400) - 1) * 100       # движение за 20 ч до 4-часового окна
    w4 = win(14400); c4 = c1[w4]; h4 = h1[w4]; l4 = l1[w4]
    if len(c4) > 60:
        up = s["rule"] == "1"
        lr = np.log(c4); x = np.arange(len(lr)); r = np.corrcoef(x, lr)[0, 1]; f["r2_4h"] = r * r
        f["eff_4h"] = abs(lr[-1] - lr[0]) / np.abs(np.diff(lr)).sum()           # 1 = идеально ровный ход, 0 = пила
        c15 = c4[::15]; r15 = np.diff(np.log(c15)) * 100
        mv = (p / c4[0] - 1) * 100
        f["max15_4h"] = (r15.max() if up else -r15.min()) if len(r15) else np.nan
        hr = [(c4[min(k + 60, len(c4) - 1)] / c4[k] - 1) * 100 for k in range(0, len(c4) - 1, 5)]
        f["max1h_4h"] = max(hr) if up else -min(hr)
        f["impulse_share"] = f["max1h_4h"] / abs(mv) if mv else np.nan          # доля движения за 4 ч, сделанная за лучший час
        f["n_dir15_4h"] = float(np.mean(r15 > 0) if up else np.mean(r15 < 0))
        ext = np.argmax(h4) if up else np.argmin(l4)
        f["min_since_ext4h"] = len(c4) - ext
        f["from_ext4h"] = (p / (h4.max() if up else l4.min()) - 1) * 100
        f["range_4h"] = (h4.max() / l4.min() - 1) * 100
    w24 = win(86400)
    if w24.sum() > 600:
        f["from_high24"] = (p / h1[w24].max() - 1) * 100; f["from_low24"] = (p / l1[w24].min() - 1) * 100
        rng = h1[w24].max() - l1[w24].min(); f["pos24"] = (p - l1[w24].min()) / rng if rng else np.nan
        vw = (q1[w24].sum() / v1[w24].sum()) if v1[w24].sum() else np.nan; f["vs_vwap24"] = (p / vw - 1) * 100 if vw else np.nan
        f["vol15_24h"] = np.std(np.diff(np.log(c1[w24][::15]))) * 100
    if len(cK) > 100:
        f["rsi15"] = rsi(np.append(cK, p)); c1h = np.append(cK[3::4][-60:], p); f["rsi1h"] = rsi(c1h)
        m20 = cK[-20:].mean(); sd = cK[-20:].std(); f["bb_pct15"] = (p - (m20 - 2 * sd)) / (4 * sd) if sd else np.nan
        last = K[-1]; rg = last[2] - last[3]
        f["upwick_last15"] = (last[2] - max(last[1], last[4])) / rg if rg else 0; f["lowwick_last15"] = (min(last[1], last[4]) - last[3]) / rg if rg else 0
        f["body_last15"] = (last[4] / last[1] - 1) * 100
    # объёмы
    q24 = q1[w24].sum(); f["qv24_musd"] = q24 / 1e6
    for lab, T in (("15m", 900), ("1h", 3600), ("4h", 14400)):
        w = win(T); f[f"vrel_{lab}"] = (q1[w].sum() / T) / (q24 / 86400) if q24 else np.nan
        f[f"tbuy_{lab}"] = b1[w].sum() / q1[w].sum() if q1[w].sum() else np.nan
    f["tbuy_24h"] = b1[w24].sum() / q24 if q24 else np.nan
    if len(qK) > 96 * 8: f["vrel_24h_vs_7d"] = qK[-96:].sum() / (qK[-96 * 8:-96].sum() / 7) if qK[-96 * 8:-96].sum() else np.nan
    f["avg_trade_rel_1h"] = (q1[win(3600)].sum() / max(n1[win(3600)].sum(), 1)) / (q24 / max(n1[w24].sum(), 1)) if q24 else np.nan
    # объём на росте: доля объёма в 4 ч, пришедшая на свечи по направлению движения
    if len(c4) > 60:
        dirm = (c1[w4] > o1[w4]) if s["rule"] == "1" else (c1[w4] < o1[w4]); f["vol_dir_share_4h"] = q1[w4][dirm].sum() / q1[w4].sum() if q1[w4].sum() else np.nan
    # метрики: OI, LSR
    if M is not None:
        M = M[M[:, 0] <= te - 300]
        def mat(T, col):
            k = np.searchsorted(M[:, 0], T, "right") - 1
            return M[k, col] if k >= 0 and T - M[k, 0] <= 1800 else np.nan
        oi = mat(te, 2); f["oi_musd"] = oi / 1e6; f["oi_to_qv24"] = oi / q24 if q24 else np.nan
        for lab, T in (("15m", 900), ("1h", 3600), ("4h", 14400), ("24h", 86400)):
            f[f"oi_ch_{lab}"] = (oi / mat(te - T, 2) - 1) * 100
            f[f"lsr_ch_{lab}"] = mat(te, 5) / mat(te - T, 5) - 1
            f[f"toppos_ch_{lab}"] = mat(te, 4) / mat(te - T, 4) - 1
        f["lsr"] = mat(te, 5); f["top_acc"] = mat(te, 3); f["top_pos"] = mat(te, 4); f["top_vs_all"] = f["top_pos"] / f["lsr"] if f["lsr"] else np.nan
        tk = M[M[:, 0] > te - 3600, 6]; f["taker_ratio_1h"] = np.nanmean(tk) if len(tk) else np.nan
        tk = M[M[:, 0] > te - 900, 6]; f["taker_ratio_15m"] = np.nanmean(tk) if len(tk) else np.nan
        f["oi_ch_per_price_4h"] = f["oi_ch_4h"] / f["ch_4h"] if f.get("ch_4h") else np.nan
    if P is not None:
        P = P[(P[:, 0] + 300 <= te)]
        for lab, T in (("1h", 3600), ("4h", 14400), ("24h", 86400)):
            x = P[P[:, 0] >= te - T, 4]; x = x[x != 0]; f[f"prem_{lab}"] = x.mean() * 100 if len(x) else np.nan
    fh = fh_entry(s); f["fund_h"] = fh * 100 if fh is not None else np.nan
    F = FUND.get(sym)
    if F is not None:
        x = F[(F[:, 0] <= te) & (F[:, 0] > te - 86400)]; f["fund_24h_sum"] = x[:, 1].sum() * 100 if len(x) else 0
        x = F[(F[:, 0] <= te - 86400) & (F[:, 0] > te - 4 * 86400)]; f["fund_prev3d_sum"] = x[:, 1].sum() * 100 if len(x) else 0
        k = np.searchsorted(F[:, 0], te) - 1; f["fund_interval_h"] = (F[k, 0] - F[k - 1, 0]) / 3600 if k >= 1 else np.nan
        f["min_to_funding"] = ((F[k, 0] + f["fund_interval_h"] * 3600 - te) / 60) if k >= 1 else np.nan
    # рынок
    kb = np.searchsorted(BTC[:, 0] + 900, te, "right") - 1
    for lab, n in (("1h", 4), ("4h", 16), ("24h", 96)): f[f"btc_{lab}"] = (BTC[kb, 4] / BTC[kb - n, 4] - 1) * 100
    dt = datetime.datetime.fromtimestamp(te, UTC); f["hour"] = dt.hour; f["weekday"] = dt.weekday()
    f["listing_days"] = (te - tK[0]) / 86400 if tK[0] > datetime.datetime(2026, 2, 2, tzinfo=UTC).timestamp() else 999
    f["price_usd"] = p
    # исходы (по одной сделке, без портфельных правил)
    r = trade(s, 6, 20); f["y_kind"] = r["kind"]; f["y_stop"] = int(r["kind"] == "стоп"); f["y_pnl"] = r["pnl"]; f["y_hours"] = r["hours"]
    r = trade(s, None, 20); f["y_up20_48h"] = int(r["kind"] == "стоп")         # вынос +20% за 48 ч независимо от тейка
    f["y_maxup48"] = r["maxup"]
    r = trade(s, None, 25); f["y_pnl_notp25"] = r["pnl"]
    return f

def job(s):
    try:
        f = feats(s)
    except Exception as e:
        print("ошибка", s["sym"], s["ep"], repr(e), flush=True); return None
    if f is None: return None
    return {"sym": s["sym"], "ep": s["ep"], "rule": s["rule"], **CH.get((s["sym"], s["ep"]), {}), **f}
with ThreadPoolExecutor(12) as ex:
    out = [x for x in ex.map(job, SIG) if x]
pd.DataFrame(out).to_csv("features.csv", index=False); print("готово", len(out), "из", len(SIG))
