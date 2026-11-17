"""s127 — 🇰🇷🆕 вне выборки 2022–2024 гг. (правило — ВЫВОДЫ.md, записано до расчёта). Листинг — первая часовая свеча
рынка к воне в кэше s88/oos/kc (не раньше 2 сут после начала кэша); фьючерс Binance ≥ суток до неё (MC_K = s117/k_oos.pkl);
шорт на закрытии 15-мин свечи в конце первого часа торгов, 7 сут, стоп 50% (s15/common.trade); плацебо — та же монета
за 45/90/135 сут. Запуск из ~/mc_oos: MC_K=… MC_F=… MC_CUT=2023-10-01 python3 <repo>/research/s127/kl_oos.py"""
import glob
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import fut_of, live, trade  # noqa: E402
from oi_test import CUT, DAY, ct, idx_at  # noqa: E402

SRC = "/home/user/mc_data/s88/oos/kc"
EX = dict(tp=None, sl=0.50, hold_h=168)


def main():
    first = {}
    t_min = None
    for ex in ("upbit", "bithumb"):
        for f in glob.glob(f"{SRC}/{ex}/KRW-*.pkl"):
            x = pickle.load(open(f, "rb"))
            if x is None or not len(x["t"]):
                continue
            t0 = int(x["t"][0]); coin = os.path.basename(f)[4:-4]
            t_min = t0 if t_min is None else min(t_min, t0)
            first.setdefault(coin, []).append((t0, ex))
    rows = []
    for coin, lst in first.items():
        s, _ = fut_of(coin)
        if not s:
            continue
        lo, hi = live(s)
        last = -1e18
        for t0, ex in sorted(lst):
            if t0 < t_min + 2 * DAY or t0 - last < 30 * DAY:
                continue
            last = t0
            T = t0 + 3600                                     # конец первого часа торгов к воне
            if lo > t0 - DAY or T + 8 * DAY > hi:
                continue
            i = idx_at(s, T)
            if i is None:
                continue
            x = trade(s, i, **EX)
            if not x:
                continue
            p = [y["net"] for dd in (45, 90, 135) if (j := idx_at(s, T - dd * DAY)) is not None and (y := trade(s, j, **EX))]
            rows.append(dict(s=s, ex=ex, t=float(T), net=x["net"], why=x["why"], pl=np.mean(p) if p else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle("s127_kl.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    m, t, n = ct(X.net, X.t); dp, tp, _ = ct(X.net - X.pl, X.t); h1, h2 = X[X.t < CUT], X[X.t >= CUT]
    print(f"🇰🇷🆕 вне выборки: листингов {n} ({n / months:.1f} в мес.; Upbit {int((X.ex == 'upbit').sum())}, Bithumb "
          f"{int((X.ex == 'bithumb').sum())}), шорт 7 сут {m:+.2%} (t {t:+.1f}), в плюсе {(X.net > 0).mean():.0%}, стопов "
          f"{(X.why == 'стоп').mean():.0%} | половины {h1.net.mean():+.2%} ({len(h1)}) / {h2.net.mean():+.2%} ({len(h2)}) | "
          f"плацебо {X.pl.mean():+.2%}, разница {dp:+.2%} (t {tp:+.1f})")


if __name__ == "__main__":
    main()
