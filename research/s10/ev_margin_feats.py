"""Признаки займа для событий MarginData (s9/md_events.pkl): интенсивность займа (BOR к объёму фьючерса за сутки), z-оценка BOR
монеты к её же значениям за 30 дней (как B.Z у автора), изменение BOR за 1 и 4 ч (BΔ%) и его z-оценка (BΔZ), доля отдачи,
CHNG (с 09.2025), рыночный фон (монет в канале, суммарный BOR по альтам и его z-оценка за 30 дней), ончейн-приток токена
на Binance за 1 и 3 дня (DefiLlama). → s10/ev_margin.pkl"""
import json, re, pickle, datetime
import numpy as np, pandas as pd
P = pd.read_pickle("s9/md_events.pkl")[["s", "t", "c_v24"]].drop_duplicates(["s", "t"])
m = pickle.load(open("s7/margin.pkl", "rb")); G, PT = m["G"], m["PT"]
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
# CHNG из сырых постов (формат с 02.09.2025)
chng = {}
for fn in ("posts_new.jsonl", "posts_oct.jsonl", "posts_oct2.jsonl", "posts.jsonl"):
    for ln in open(fn):
        x = json.loads(ln)
        if len(x) < 3 or not isinstance(x[2], str) or "CHNG" not in x[2][:200]: continue
        t = datetime.datetime.fromisoformat(x[1]).timestamp()
        for l in x[2].splitlines()[2:]:
            p = l.split()
            if len(p) == 5 and re.match(r"^[A-Z0-9]+$", p[0]):
                try: chng.setdefault(p[0], []).append((t, float(p[4])))
                except ValueError: pass
chng = {k: np.array(sorted(v)) for k, v in chng.items()}
# рыночный фон: суммарный BOR по всем монетам в каждом посте
tot = {}
for c, arr in G.items():
    for t, b in zip(arr[:, 0], arr[:, 1]):
        if np.isfinite(b): tot[t] = tot.get(t, 0.0) + b
TT = np.array(sorted(tot)); TV = np.array([tot[t] for t in TT])
cnt = {}
for c, arr in G.items():
    for t in arr[:, 0]: cnt[t] = cnt.get(t, 0) + 1
TC = np.array([cnt[t] for t in TT])
Q = pd.read_pickle("s10/cex_qty.pkl").iloc[:-1]
rows = []
for s, T, v24 in zip(P.s, P.t, P.c_v24):
    c = strip(s); arr = G.get(c) if c in G else G.get(s)
    r = dict(s=s, t=T)
    if arr is not None:
        tt, bor, rep = arr[:, 0], arr[:, 1], arr[:, 2]
        k = np.searchsorted(tt, T, "right") - 1
        if k >= 0 and T - tt[k] <= 1800:
            B = bor[k]; r["bor_vol"] = B / max(v24, 1); r["rep_share"] = rep[k] / max(B, 1)
            h = (tt >= T - 30 * 86400) & (tt <= T)
            hb = bor[h]
            if len(hb) >= 50 and np.nanstd(hb) > 0: r["bz"] = (B - np.nanmean(hb)) / np.nanstd(hb)
            for nm, dt in (("1h", 3600), ("4h", 14400)):
                kp = np.searchsorted(tt, T - dt, "right") - 1
                if kp >= 0 and T - dt - tt[kp] <= 1800: r[f"bd_{nm}"] = B / max(bor[kp], 1) - 1
            # BΔZ: z-оценка часового изменения BOR к часовым изменениям за 30 дней
            if "bd_1h" in r and len(hb) >= 50:
                th = tt[h]; kk = np.searchsorted(tt, th - 3600, "right") - 1; ok = (kk >= 0) & (th - 3600 - tt[np.maximum(kk, 0)] <= 1800)
                d1 = bor[h][ok] / np.maximum(bor[np.maximum(kk, 0)][ok], 1) - 1
                if len(d1) >= 30 and np.std(d1) > 0: r["bdz"] = (r["bd_1h"] - np.mean(d1)) / np.std(d1)
    ch = chng.get(c)
    if ch is not None:
        k = np.searchsorted(ch[:, 0], T, "right") - 1
        if k >= 0 and T - ch[k, 0] <= 1800: r["chng"] = ch[k, 1]
    k = np.searchsorted(TT, T, "right") - 1
    if k >= 0:
        r["mkt_n"] = TC[k]; r["mkt_bor"] = TV[k]
        h = (TT >= T - 30 * 86400) & (TT <= T)
        if h.sum() > 100: r["mkt_bz"] = (TV[k] - TV[h].mean()) / TV[h].std()
    if c in Q.columns:
        d = pd.Timestamp(datetime.datetime.utcfromtimestamp(T).date())
        q = Q[c]
        for nm, n in (("1d", 1), ("3d", 3)):
            a, b = q.get(d), q.get(d - pd.Timedelta(days=n))
            if a is not None and b is not None and np.isfinite(a) and np.isfinite(b) and b > 0: r[f"cex_{nm}"] = a / b - 1
    rows.append(r)
D = pd.DataFrame(rows); D.to_pickle("s10/ev_margin.pkl")
print(len(D), D.notna().mean().round(2).to_dict())
print(D.describe(percentiles=[.1, .5, .9]).T[["10%", "50%", "90%"]].round(3).to_string())
