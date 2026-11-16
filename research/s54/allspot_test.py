"""s54 — суммарная доля спота (Binance + Upbit/Bithumb + Coinbase) в пампах вне 🇰🇷 и 🛒 (гипотеза — ВЫВОДЫ.md, записана
до расчёта). Пампы — s15/kr_pumps.pkl; оборот за последний полный час до закрытия свечи пампа: спот Binance (s23/spot1h.pkl),
Корея (s15/kr_panel.pkl, колонка kr), Coinbase (s46/cb1h.pkl), фьючерс (s2/k2y.pkl). Только пампы с долей Кореи < 20%
и долей спота Binance < 25,9%. Трети суммарной доли — по таким пампам первой половины. Шорт 10/25/48, одна сделка
на монету за 48 ч; плацебо — та же монета за 45/90/135 сут. Запуск из папки с данными."""
import os
import pickle
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, fut_of, trade  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402

EX = dict(tp=0.10, sl=0.25, hold_h=48)


def main():
    PU = pickle.load(open("s15/kr_pumps.pkl", "rb"))
    SP = pickle.load(open("s23/spot1h.pkl", "rb"))
    KP = pickle.load(open("s15/kr_panel.pkl", "rb"))
    CB = pickle.load(open("s46/cb1h.pkl", "rb"))
    cb = {}
    for b, d in CB.items():
        s, _ = fut_of(b)
        if s:
            cb[s] = d.set_index("T").usd
    rows = []
    for s, pj in PU.items():
        if s not in K or not len(pj):
            continue
        a = K[s]; Tend = a["t"].astype(np.int64) + 900
        perp = pd.Series(a["qv"].astype(float)).groupby(((Tend - 1) // 3600 + 1) * 3600).sum()
        spv = pd.Series(SP[s][:, 1], index=SP[s][:, 0].astype(np.int64) + 3600) if s in SP else None
        krv = KP[s].set_index("T").kr if s in KP else None
        cbv = cb.get(s)
        last = -1e18
        for j in pj:
            Tp = int(a["t"][j]) + 900
            if Tp - last < 48 * 3600:
                continue
            H = (Tp // 3600) * 3600
            pv = float(perp.get(H, np.nan))
            if not pv == pv:
                continue
            vs = float(spv.get(H, 0.0)) if spv is not None else 0.0
            vk = float(krv.get(H, 0.0)) if krv is not None else 0.0
            vc = float(cbv.get(H, 0.0)) if cbv is not None else 0.0
            vs, vk, vc = (0.0 if v != v else v for v in (vs, vk, vc))
            x = trade(s, j, **EX)
            if x is None:
                continue
            last = Tp
            p = [y["net"] for dd in (45, 90, 135) if j - dd * 96 >= 96 and (y := trade(s, j - dd * 96, **EX))]
            rows.append(dict(s=s, t=Tp, bin_share=vs / max(vs + pv, 1.0), kr_share=vk / max(vk + pv, 1.0),
                             all_share=(vs + vk + vc) / max(vs + vk + vc + pv, 1.0), net=x["net"], pl=np.mean(p) if p else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle("s54/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    R = X[(X.kr_share < 0.20) & (X.bin_share < 0.259)]
    q1, q2 = R[R.t < CUT].all_share.quantile([1 / 3, 2 / 3])
    print(f"Пампов со сделкой: {len(X)}; вне 🇰🇷 и 🛒: {len(R)} ({len(R) / months:.0f} в месяц); трети суммарной доли спота"
          f" по первой половине: {q1:.1%} и {q2:.1%}")

    def line(lab, x):
        if len(x) < 8:
            return f"  {lab:40s} мало ({len(x)})"
        m, t, n = ct(x.net, x.t); dp, tp, _ = ct(x.net - x.pl, x.t)
        a, b = x[x.t < CUT].net.mean(), x[x.t >= CUT].net.mean()
        return (f"  {lab:40s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x.net > 0).mean():3.0%} |"
                f" половины {a:+6.2%} / {b:+6.2%} | плацебо {x.pl.mean():+6.2%}, разница {dp:+6.2%} (t {tp:+4.1f})")

    print(line("нижняя треть суммарной доли спота", R[R.all_share < q1]))
    print(line("средняя треть", R[(R.all_share >= q1) & (R.all_share < q2)]))
    print(line("ОСНОВНАЯ: верхняя треть", R[R.all_share >= q2]))
    print(line("для сравнения: пампы 🛒 (спот Binance ≥ 25,9%)", X[X.bin_share >= 0.259]))


if __name__ == "__main__":
    main()
