"""s188 — проба: что дают ставки займа маржи Binance на трёх периодах (без доходов, сделок и плацебо).

Ставки: 10.2020–09.2024 — выборка 60 оборотных монет (bn_rates_old.py, /home/user/mc_data/s188/bnrates), с 09.2024 —
кэш s11 (/home/user/mc_data/s11/rates, все монеты маржи). Ряды приводятся к суткам UTC (ставка на конец суток).
Считается:
  - живость ряда: доля суток, когда ставка изменилась; число различных значений;
  - загрузка x = ставка / 10-й перцентиль своих прошлых 30 сут (как s40); события «x ≥ 3 впервые за 7 сут» (В1 s40)
    и «x ≥ 3 при фандинге за 7 сут ≥ 0» (направленный займ, s11) — в месяц;
  - недельная корзина «дорогой займ при фандинге ≥ 0»: понедельник, монеты с x ≥ 1,5 и f7 ≥ 0, сколько их на срез
    (если медиана < 5, корзина из 5 не набирается);
  - пересечение событий со входами журналов (±7 сут).
Для 2024–2026 — и выборка 60, и все монеты маржи с перпом (масштаб частот выборки). Запуск: python3 -I bn_rates_probe.py."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/margin_call/research/s183/study")
import common183 as C  # noqa: E402

DAY = 86400
OLD = "/home/user/mc_data/s188/bnrates"
NEW = "/home/user/mc_data/s11/rates"


def load(c):
    rows = []
    for d in (OLD, NEW):
        fn = f"{d}/{c}.csv"
        if os.path.exists(fn) and os.path.getsize(fn) > 0:
            x = pd.read_csv(fn, header=None, names=["t", "r"])
            if len(x):
                rows.append(x)
    if not rows:
        return None
    x = pd.concat(rows).drop_duplicates("t").sort_values("t")
    x["d"] = (x.t // DAY) * DAY
    s = x.groupby("d").r.last()
    full = np.arange(s.index.min(), s.index.max() + DAY, DAY)
    return s.reindex(full).ffill()


def main(full=False):
    coins = sorted(f[:-4] for f in os.listdir(OLD))
    if full:                                   # 2024–2026: все монеты маржи с перпом (кэш s11) — масштаб выборки 60
        perps = set(pd.read_pickle(f"{C.OUT}/daily_2024–2026.pkl").s.unique())
        coins = sorted(f[:-4] for f in os.listdir(NEW) if f[:-4] in perps and f[:-4] not in C.bad_set())
    R = {c: load(c) for c in coins}
    R = {c: s for c, s in R.items() if s is not None and len(s) > 60}
    print("монет с рядом:", len(R), "(все монеты маржи с перпом, только 2024–2026)" if full else "(выборка 60)")
    for per in (["2024–2026"] if full else C.PERS):
        t0, t1 = C.ts(C.PER[per]["t0"]), C.ts(C.PER[per]["t1"])
        dp = pd.read_pickle(f"{C.OUT}/daily_{per}.pkl")
        dp = dp[dp.s.isin(R.keys())]
        f7 = {s: x.set_index("d").fsum.fillna(0).rolling(7, min_periods=5).sum() for s, x in dp.groupby("s")}
        J = C.journals(per)
        jt = {s: np.sort(x.t.values) for s, x in J.groupby("s")}
        mon = C.months(per)
        live, ndist, ev1, ev2, nbask = [], [], [], [], []
        for c, s in R.items():
            s = s[(s.index >= t0 - 40 * DAY) & (s.index < t1)]
            if len(s) < 60:
                continue
            ins = s[s.index >= t0]
            live.append((ins.diff() != 0).mean())
            ndist.append(ins.nunique())
            fl = s.rolling(30, min_periods=20).quantile(0.10).shift(1)
            x = s / fl
            hit = x[(x >= 3) & (x.index >= t0)].index
            last = -10 ** 12
            for t in hit:
                if t - last >= 7 * DAY:
                    ev1.append((c, t))
                    ff = f7.get(c)
                    if ff is not None and t in ff.index and ff.loc[t] >= 0:
                        ev2.append((c, t))
                    last = t
        # недельная корзина «x ≥ 1,5 и f7 ≥ 0»
        for m in C.mondays(per):
            k = 0
            for c, s in R.items():
                if m - DAY not in s.index:
                    continue
                fl = s[(s.index < m) & (s.index >= m - 31 * DAY)]
                if len(fl) < 20:
                    continue
                xx = s.loc[m - DAY] / max(np.quantile(fl.values, 0.10), 1e-12)
                ff = f7.get(c)
                if xx >= 1.5 and ff is not None and (m - DAY) in ff.index and ff.loc[m - DAY] >= 0:
                    k += 1
            nbask.append(k)

        def ov(ev):
            return np.mean([c in jt and np.any(np.abs(jt[c] - t) <= 7 * DAY) for c, t in ev]) if ev else np.nan
        print(f"\n== {per}: монет {len(live)}; доля суток со сменой ставки — медиана {np.median(live):.0%} "
              f"(p10 {np.quantile(live, .1):.0%}, p90 {np.quantile(live, .9):.0%}); различных значений за период — "
              f"медиана {np.median(ndist):.0f}")
        print(f"  x ≥ 3 впервые за 7 сут: {len(ev1)} событий, {len(ev1) / mon:.1f} в месяц на {len(live)} монет; "
              f"вход журнала ±7 сут {ov(ev1):.0%}")
        dyn = C.ts("2023-02-20")
        if t0 < dyn < t1:
            e1d = [z for z in ev1 if z[1] >= dyn]
            e2d = [z for z in ev2 if z[1] >= dyn]
            md = (t1 - dyn) / (30.4 * DAY)
            print(f"    из них после 20.02.2023 (часовая ставка): {len(e1d)} ({len(e1d) / md:.1f} в месяц), "
                  f"при f7 ≥ 0 — {len(e2d)} ({len(e2d) / md:.1f} в месяц)")
        print(f"  то же при f7 ≥ 0 (направленный займ): {len(ev2)} событий, {len(ev2) / mon:.1f} в месяц; "
              f"вход журнала ±7 сут {ov(ev2):.0%}")
        nb = np.array(nbask)
        print(f"  корзина «x ≥ 1,5 и f7 ≥ 0» на понедельник: монет медиана {np.median(nb):.0f}, p25 "
              f"{np.quantile(nb, .25):.0f}, p75 {np.quantile(nb, .75):.0f}; срезов с ≥ 5 монетами {np.mean(nb >= 5):.0%}")


if __name__ == "__main__":
    main()
    main(full=True)
