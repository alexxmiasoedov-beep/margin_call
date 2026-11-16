"""s46 — доля Coinbase в пампе (гипотеза — ВЫВОДЫ.md, записана до скачивания). Пампы — s15/kr_pumps.pkl (+15% за ≤ 2 ч
из покоя, 15-мин свечи), доля Coinbase = Coinbase / (Coinbase + фьючерс Binance) за последний полный час до закрытия
свечи пампа; доля Кореи — s15/kr_panel.pkl. Шорт с закрытия свечи пампа, тейк 10% / стоп 25% / 48 ч (как 🇰🇷), одна сделка
на монету за 48 ч; плацебо — та же монета за 45/90/135 сут. Запуск из папки с данными после cb_fetch.py."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, fut_of, trade  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402

EX = dict(tp=0.10, sl=0.25, hold_h=48)


def bin_hourly(s):
    a = K[s]; T = (a["t"].astype(np.int64) + 900)
    H = ((T - 1) // 3600 + 1) * 3600                          # конец часа, в который входит свеча
    return pd.Series(a["qv"].astype(float)).groupby(H).sum()


def main():
    PU = pickle.load(open("s15/kr_pumps.pkl", "rb"))
    KP = pickle.load(open("s15/kr_panel.pkl", "rb"))
    CB = pickle.load(open("s46/cb1h.pkl", "rb"))
    cb_of = {}
    for b, d in CB.items():
        s, _ = fut_of(b)
        if s:
            cb_of[s] = d.set_index("T").usd
    rows = []
    for s, pj in PU.items():
        if s not in K or not len(pj):
            continue
        bh = bin_hourly(s)
        cb = cb_of.get(s)
        if cb is not None:
            sh = (cb / (cb + bh.reindex(cb.index).fillna(0)).clip(lower=1.0)).dropna()
            norm = sh.shift(1).rolling(168, min_periods=120).median()
        kp = KP.get(s)
        last = -1e18
        for j in pj:
            Tp = int(K[s]["t"][j]) + 900
            if Tp - last < 48 * 3600:
                continue
            H = (Tp // 3600) * 3600                            # конец последнего полного часа
            share = np.nan; nm = np.nan
            if cb is not None:
                share = float(sh.get(H, np.nan)) if H in sh.index else 0.0
                nm = float(norm.get(H, np.nan)) if H in norm.index else np.nan
            kr = np.nan
            if kp is not None:
                Tv = kp["T"].values; k = int(np.searchsorted(Tv, Tp, side="right")) - 1
                kr = float(kp["share"].values[k]) if k >= 0 and Tp - Tv[k] < 3600 else np.nan
            x = trade(s, j, **EX)
            if x is None:
                continue
            last = Tp
            p = []
            for dd in (45, 90, 135):
                jj = j - dd * 96
                if jj >= 96:
                    y = trade(s, jj, **EX)
                    if y:
                        p.append(y["net"])
            rows.append(dict(s=s, t=Tp, on_cb=cb is not None, share=share, norm=nm, kr=kr, net=x["net"],
                             pl=np.mean(p) if p else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle("s46/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Пампов со сделкой: {len(X)} за {months:.1f} мес.; монета на Coinbase — {X.on_cb.sum()}")

    def line(lab, x):
        if len(x) < 8:
            return f"  {lab:46s} мало ({len(x)})"
        m, t, n = ct(x.net, x.t); dp, tp, _ = ct(x.net - x.pl, x.t)
        h1, h2 = x[x.t < CUT].net.mean(), x[x.t >= CUT].net.mean()
        return (f"  {lab:46s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x.net > 0).mean():3.0%} |"
                f" половины {h1:+6.2%} / {h2:+6.2%} | плацебо {x.pl.mean():+6.2%}, разница {dp:+6.2%} (t {tp:+4.1f})")

    print(line("все пампы", X))
    print(line("монеты нет на Coinbase", X[~X.on_cb]))
    print(line("на Coinbase, доля < 5%", X[X.on_cb & (X.share < 0.05)]))
    print(line("на Coinbase, доля 5–20%", X[X.on_cb & (X.share >= 0.05) & (X.share < 0.2)]))
    print(line("ОСНОВНАЯ: доля Coinbase ≥ 20%", X[X.share >= 0.2]))
    print(line("  то же без пампов с долей Кореи ≥ 20%", X[(X.share >= 0.2) & ~(X.kr >= 0.2)]))
    print(line("вариант: доля ≥ 10%", X[X.share >= 0.1]))
    print(line("вариант: доля ≥ 30%", X[X.share >= 0.3]))
    print(line("вариант: доля ≥ 20% и ≥ 3× обычной", X[(X.share >= 0.2) & (X.share >= 3 * X.norm)]))
    print(line("для сравнения: доля Кореи ≥ 20% (🇰🇷)", X[X.kr >= 0.2]))


if __name__ == "__main__":
    main()
