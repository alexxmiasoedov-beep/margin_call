"""s106 — перевод фандинга на часовой интервал на полу: лонг (гипотеза — ВЫВОДЫ.md, записана до расчёта). События из
s2/fund2y.pkl: начисление T со ставкой ≤ −1,5% после интервала ≥ 4 ч, следующее — через 1 ч (с 02.05.2025). Лонг
с закрытия 15-мин свечи в T + 30 мин на 8 ч (ещё 4 и 24 ч), стоп −15%, без тейка (s15/common.trade, side=+1).
Контроль — такие же начисления до 02.05.2025 (перевода не было) и плацебо той же монеты за 45/90/135 сут.
Запуск из папки с данными: python3 <repo>/research/s106/hourly_test.py"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, trade  # noqa: E402
from oi_test import CUT, DAY, ct, idx_at  # noqa: E402

RULE = pd.Timestamp("2025-05-02", tz="UTC").timestamp()
HOLDS = (8, 4, 24)


def events():
    F = pickle.load(open("s2/fund2y.pkl", "rb"))
    out = []
    for s, a in F.items():
        if s not in K or len(a) < 3:
            continue
        t = a[:, 0].astype(np.int64); t = np.where(t > 1e11, t // 1000, t); r = a[:, 2].astype(float)
        for i in range(1, len(t) - 1):
            if t[i] - t[i - 1] < 4 * 3600 - 100:
                continue                                     # до T интервал был ≥ 4 ч
            sw = abs((t[i + 1] - t[i]) - 3600) <= 100        # следующее начисление через 1 ч — перевели
            out.append((s, int(t[i]), r[i], sw))
    return pd.DataFrame(out, columns=["s", "T", "rate", "sw"])


def deal(s, T, h, side=1):
    i = idx_at(s, T + 1800)
    if i is None:
        return None
    return trade(s, i, tp=None, sl=0.15, hold_h=h, side=side)


def main():
    E = events()
    groups = {
        "≤ −1,5%, перевод на 1 ч (основная)": E[(E["T"] >= RULE) & (E.rate <= -0.015) & E.sw],
        "< 0, перевод на 1 ч (шире)": E[(E["T"] >= RULE) & (E.rate < 0) & E.sw],
        "≤ −1,5% до 02.05.2025 (контроль)": E[(E["T"] < RULE) & (E.rate <= -0.015)],
        "≤ −1,5% после 02.05.2025 без перевода": E[(E["T"] >= RULE) & (E.rate <= -0.015) & ~E.sw],
    }
    rows = []
    for g, x in groups.items():
        for s, T, rate in zip(x.s, x["T"], x.rate):
            d = dict(g=g, s=s, t=float(T), rate=rate)
            for h in HOLDS:
                y = deal(s, T, h)
                d[f"L{h}"] = y["net"] if y else np.nan
                d[f"f{h}"] = y["fund"] if y else np.nan
                if h == 8 and y:
                    d["why"] = y["why"]
                p = [z["net"] for dd in (45, 90, 135) if (z := deal(s, T - dd * DAY, h))]
                d[f"pl{h}"] = np.mean(p) if p else np.nan
            rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle("s106/trades.pkl")
    up = E[(E["T"] >= RULE) & (E.rate >= 0.015) & E.sw]
    print(f"переводов на 1 ч у потолка (≥ +1,5%): {len(up)} — только для сведения")
    for h in HOLDS:
        print(f"\n=== лонг с T + 30 мин на {h} ч ===")
        for g in groups:
            x = X[(X.g == g) & X[f"L{h}"].notna()]
            if len(x) < 8:
                print(f"  {g:40s} n={len(x)}")
                continue
            months = max((x.t.max() - x.t.min()) / (30.4 * DAY), 1)
            m, t, n = ct(x[f"L{h}"], x.t); dp, tp, _ = ct(x[f"L{h}"] - x[f"pl{h}"], x.t)
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            print(f"  {g:40s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[f'L{h}'] > 0).mean():3.0%} "
                  f"фандинг лонгу {x[f'f{h}'].mean():+6.2%} | половины {ct(h1[f'L{h}'], h1.t)[0]:+6.2%} / "
                  f"{ct(h2[f'L{h}'], h2.t)[0]:+6.2%} | плацебо {x[f'pl{h}'].mean():+6.2%}, разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
