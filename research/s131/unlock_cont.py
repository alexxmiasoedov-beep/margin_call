"""s131 — шорт T → T + 7 сут после разлока ≥ 1% при фандинге за неделю до разлока F7 ≤ −0,5% (протокол — ВЫВОДЫ.md,
записан до расчёта). Разлоки CMC 01.2023–09.2024 (кэш s28/ev_old и s28/hist_old, как s28/unlock_oos.py), свечи 15 мин
и фандинг — месячные архивы data.binance.vision (кэш s26/old). Плацебо — та же монета за 45/90/135 сут без разлоков
≥ 1% в ±10 сут; признак F7 считается на дату плацебо. Запуск из папки с данными: python3 <repo>/research/s131/unlock_cont.py"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s28"))
import unlock_oos as U  # noqa: E402

DAY = 86400
F_MAX = -0.005                                           # основная группа: F7 ≤ −0,5%


def f7(f, T):
    if f is None or not len(f):
        return np.nan
    return float(f[(f[:, 0] >= T - 7 * DAY) & (f[:, 0] < T), 1].sum())


def deal(s, T, r=None):
    ms = U.months(T - 10 * DAY, T + 9 * DAY)
    k = U.series("klines", s, ms)
    if k is None or k[0, 0] > T - 8 * DAY:              # фьючерс торгуется с T − 8 сут
        return None
    if r is not None and not U.px_ok(k, r):
        return None
    f = U.series("fundingRate", s, ms)
    btc = U.series("klines", "BTCUSDT", ms)
    x = U.trade(k, f, btc, T, 7, 0.25, -1)
    if x is None:
        return None
    x["F7"] = f7(f, T)
    return x


def main():
    E = U.build(U.tokens())
    W = E[(E.t >= U.T0) & (E.t < U.T1) & (E["size"] >= 1)].sort_values("t")
    print(f"разлоков ≥ 1% в 01.2023–09.2024: {len(W)}, монет {W.s.nunique()}", flush=True)
    need = {("BTCUSDT", m) for m in U.months(U.T0 - 150 * DAY, U.T1 + 15 * DAY)}
    for r in W.itertuples():
        for back in (0, 45, 90, 135):
            need |= {(r.s, m) for m in U.months(r.t - (back + 10) * DAY, r.t - (back - 9) * DAY)}
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda p: (U.fetch("klines", *p), U.fetch("fundingRate", *p)), sorted(need)))
    print(f"месячных архивов: {len(need)}", flush=True)
    allt = {s: E[(E.s == s) & (E["size"] >= 1)].t.values for s in E.s.unique()}
    rows, pl, last = [], [], {}
    for r in W.itertuples():
        if r.t < last.get(r.s, -1):                      # одна сделка на монету за 7 сут
            continue
        x = deal(r.s, r.t, r)
        if x is None:
            continue
        last[r.s] = r.t + 7 * DAY
        rows.append(dict(s=r.s, t=r.t, size=r.size, cliff=r.cliff, **x))
        for back in (45, 90, 135):
            tp = r.t - back * DAY
            if np.any(np.abs(allt[r.s] - tp) < 10 * DAY):
                continue
            y = deal(r.s, tp)
            if y is not None:
                pl.append(dict(s=r.s, t=tp, ev_t=r.t, back=back, ev_F7=x["F7"], **y))
    R, P = pd.DataFrame(rows), pd.DataFrame(pl)
    R.to_pickle("s131_trades.pkl"); P.to_pickle("s131_placebo.pkl")
    months = (U.T1 - U.T0) / (30.4 * DAY)
    print(f"сделок {len(R)} ({len(R) / months:.1f} в месяц); F7 ≤ −0,5% у {(R.F7 <= F_MAX).mean():.0%}, медиана F7 "
          f"{R.F7.median():+.2%}")
    print("\nШорт T → T + 7 сут, стоп +25% (2023 / 2024 — половины)")
    U.line(R[R.F7 <= F_MAX], "F7 ≤ −0,5% (основная)")
    U.line(R[R.F7 <= -0.01], "F7 ≤ −1%")
    U.line(R[R.F7 > F_MAX], "F7 > −0,5%")
    U.line(R, "все разлоки ≥ 1%")
    U.line(P[P.F7 <= F_MAX], "плацебо с F7 ≤ −0,5% на дату")
    U.line(P[P.ev_F7 <= F_MAX], "плацебо событий основной группы")
    U.line(P[P.F7 > F_MAX], "плацебо с F7 > −0,5% на дату")
    a, c = R[R.F7 <= F_MAX].net, R[R.F7 > F_MAX].net
    if len(a) > 5:
        d = a.mean() - c.mean(); se = np.sqrt(a.var() / len(a) + c.var() / len(c))
        print(f"\nосновная − (F7 > −0,5%): {d:+.2%} (t ≈ {d / se:+.1f})")
        b = P[P.F7 <= F_MAX].net
        if len(b) > 5:
            d = a.mean() - b.mean(); se = np.sqrt(a.var() / len(a) + b.var() / len(b))
            print(f"основная − плацебо с F7 ≤ −0,5%: {d:+.2%} (t ≈ {d / se:+.1f})")
    print("\nпо размеру (основная группа):")
    x = R[R.F7 <= F_MAX]
    U.line(x[x["size"] < 5], "размер 1–5%")
    U.line(x[x["size"] >= 5], "размер ≥ 5%")


if __name__ == "__main__":
    main()
