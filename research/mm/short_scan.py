"""Шорт после пампа: каждые 15 мин по монетам, где за последние сутки рост от минимума до максимума ≥ 30% (минимум раньше максимума).
Исход: −15% (тейк) / +10% (стоп), что раньше, иначе выход через 24 ч; комиссии 0,1%, вход +0,1% проскальзывания."""
import pickle, datetime, json, re, sys
import numpy as np, pandas as pd
MSK = datetime.timezone(datetime.timedelta(hours=3))
K = pickle.load(open("kaia/k15_6m.pkl", "rb"))
rx = re.compile(r'^([A-Z0-9]+)\s+([\d.]+[KMB]?)\s+([\d.]+[KMB]?)\s+([\d.]+)(?:\s+(-?[\d.]+))?\s*$')
CH = {}
for fn in ("posts.jsonl", "posts_new.jsonl", "posts_oct.jsonl"):
    for ln in open(fn):
        pid, ts, txt = json.loads(ln); ep = datetime.datetime.fromisoformat(ts).timestamp()
        for row in txt.splitlines():
            m = rx.match(row.strip())
            if m: CH.setdefault(m.group(1), []).append(ep)
CH = {s: np.array(sorted(v)) for s, v in CH.items()}
TPs, SLs, HOLD = 0.15, 0.10, 96
rows = []
for s, k in K.items():
    if len(k) < 96 * 3 + HOLD: continue
    t, o, h, l, c, v, qv = (k[:, j] for j in range(7))
    H = pd.Series(h); L = pd.Series(l)
    hh = H.rolling(96).max().values; ll = L.rolling(96).min().values
    idx = np.arange(96 * 2, len(k) - HOLD)
    cand = idx[(hh[idx] / ll[idx] >= 1.30)]
    for i in cand:
        w = slice(i - 95, i + 1); jh = i - 95 + int(np.argmax(h[w])); jl = i - 95 + int(np.argmin(l[w]))
        if jl >= jh: continue                                              # минимум раньше максимума — это был рост
        top = h[jh]; rise = top / l[jl] - 1
        p = c[i] * 0.999
        res = np.nan
        for d in range(1, HOLD + 1):
            if h[i + d] >= p * (1 + SLs): res = -SLs; break
            if l[i + d] <= p * (1 - TPs): res = TPs; break
        if not np.isfinite(res): res = 1 - c[i + HOLD] / p
        jv = jh                                                             # объём часа вершины против последнего часа
        vol_top = qv[max(jv - 3, 0):jv + 1].sum(); vol_now = qv[i - 3:i + 1].sum()
        wick = (top - max(o[jh], c[jh])) / (top - l[jh]) if top > l[jh] else 0
        hi2h = h[max(i - 7, jh + 1):i + 1].max() if i > jh else top
        ch = CH.get(s); inch = bool(ch is not None and ((ch > t[i] + 900 - 4 * 3600) & (ch <= t[i] + 900)).any())
        rows.append((s, t[i] + 900, rise, c[i] / top - 1, (i - jh) / 4, vol_now / max(vol_top, 1e-9), wick, hi2h / top - 1,
                     c[i] / c[i - 4] - 1, c[i] / c[i - 1] - 1, inch, res - 0.001))
D = pd.DataFrame(rows, columns=["sym", "te", "rise", "from_top", "h_since", "vol_fade", "wick", "lower_high", "ret_1h", "ret_15m", "inch", "pnl"])
D.to_pickle("mm/short_scan.pkl")
print(f"моментов после пампа: {len(D)}, монет {D.sym.nunique()}")
