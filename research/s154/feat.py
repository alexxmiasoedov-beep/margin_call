"""s154 — признаки теханализа, SMC и кластеров на свече входа сделок журналов (протокол — ВЫВОДЫ.md, записан до расчёта).
Сделки 2024–2026 гг.: 🛒 (s49), 🇰🇷, 🏦, 📘 (s20), 🔝 (s65), 👀 (s83), ⏰ (s88), 🌊 (s23). Признаки F1–F8 по 15-мин свечам
s2/k2y.pkl до момента входа. Итог — s154_feat.pkl в папке данных. Запуск из /home/user/mc_data."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K  # noqa: E402
from oi_test import idx_at  # noqa: E402


def trades():
    out = []
    a = pd.read_pickle("s49/trades.pkl"); a = a[a.share >= 0.26]
    out.append(pd.DataFrame(dict(j="🛒", s=a.s, te=a.t.astype(np.int64), net=a.net)))
    b = pd.read_pickle("s20/trades.pkl")
    for j, name in (("🇰🇷", "🇰🇷"), ("🏦", "🏦"), ("канал", "📘")):
        x = b[b.journal == j]
        out.append(pd.DataFrame(dict(j=name, s=x.s, te=x.te.astype(np.int64), net=x.net)))
    c = pd.read_pickle("s65/trades.pkl")
    out.append(pd.DataFrame(dict(j="🔝", s=c.s, te=c.t.astype(np.int64), net=c.S_10_25)))
    d = pd.read_pickle("s83/trades.pkl")
    out.append(pd.DataFrame(dict(j="👀", s=d.s, te=d.t.astype(np.int64), net=d.S_10_25)))
    e = pd.read_pickle("s88/trades.pkl"); e = e[e.open9 & (e.share >= 0.2) & (e.r1 >= 0.05)]   # правило ⏰
    out.append(pd.DataFrame(dict(j="⏰", s=e.s, te=e.t.astype(np.int64), net=e.S_10_25)))
    f = pd.read_pickle("s23/rule_trades.pkl"); f = f[f.rate <= -0.01]
    out.append(pd.DataFrame(dict(j="🌊", s=f.s, te=f["T"].astype(np.int64) + 900, net=f["net0.15"])))
    X = pd.concat(out, ignore_index=True).dropna(subset=["net"])
    return X[X.s.isin(K.keys())].reset_index(drop=True)


def features(s, te):
    i = idx_at(s, te)
    if i is None or i < 100:
        return None
    a = K[s]
    o, h, l, c = (a[k][i - 99:i + 1].astype(float) for k in ("o", "h", "l", "c"))
    qv, tb = a["qv"][i - 99:i + 1].astype(float), a["tb"][i - 99:i + 1].astype(float)
    if qv[-1] <= 0 or h[-1] <= l[-1]:
        return None
    rng = h[-1] - l[-1]
    d = 2 * tb - qv
    f1 = (h[-1] - max(o[-1], c[-1])) / rng
    f2 = d[-1] / qv[-1]
    f3 = d[-4:].sum() / qv[-4:].sum() if qv[-4:].sum() > 0 else np.nan
    f4 = float(c[-1] > c[-5] and d[-1] < 0)
    base = qv[-5:-1].mean()
    f5 = float(base > 0 and qv[-1] >= 2 * base and abs(c[-1] - o[-1]) <= 0.3 * rng)
    tp, w = (h[-97:] + l[-97:] + c[-97:]) / 3, qv[-97:]
    vwap = (tp * w).sum() / w.sum() if w.sum() > 0 else np.nan
    f6 = c[-1] / vwap - 1 if vwap and np.isfinite(vwap) else np.nan
    pm = h[-97:-1].max()
    f7 = float(h[-1] > pm and c[-1] < pm)
    f8 = 0.0
    for k in range(len(c) - 1, len(c) - 13, -1):            # ближайший к концу незакрытый бычий разрыв за 12 свечей
        if k - 2 < 0:
            break
        top = h[k - 2]
        if l[k] > top and (k + 1 >= len(c) or l[k + 1:].min() > top):
            f8 = c[-1] / top - 1
            break
    return dict(F1=f1, F2=f2, F3=f3, F4=f4, F5=f5, F6=f6, F7=f7, F8=f8)


def main():
    X = trades()
    rows = []
    for r in X.itertuples():
        f = features(r.s, int(r.te))
        if f:
            rows.append(dict(j=r.j, s=r.s, te=int(r.te), net=float(r.net), **f))
    F = pd.DataFrame(rows)
    F.to_pickle("s154_feat.pkl")
    print(F.groupby("j").size().to_dict())


if __name__ == "__main__":
    main()
