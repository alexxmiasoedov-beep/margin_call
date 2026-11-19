"""s190 Г2 — «конец суток ботов пробоя Upbit» (гипотеза — ВЫВОДЫ.md, записана до расчёта). По 15-мин свечам перпа:
цель суток Oₜ + 0,5·(Hₜ₋₁ − Lₜ₋₁) (сутки с 00:00 UTC), пробой — максимум свечей 00:00…23:45 выше цели. Монеты
с рынком Upbit в эти сутки и долей Upbit + Bithumb в обороте суток ≥ 20% (дневная панель s183). Шорт с закрытия свечи
23:30–23:45 до закрытия свечи 00:00–00:15 (fastbt, 0,5 ч); вариант (б) — на 30 мин раньше (22:45–23:00 → 23:30).
Контроль (а) — те же условия без пробоя. Запуск из /home/user/mc_data: [MC_K=… MC_F=…] python3 <repo>/research/s190/g2.py
<период>  → s190_g2_<период>.pkl; сводка: … g2.py report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
sys.path.insert(0, os.path.join(HERE, "..", "s182"))

DAY, OUT = 86400, "/home/user/mc_data"


def run(per):
    import fastbt as FB  # noqa: E402
    K = FB.K
    P = pd.read_pickle(f"{OUT}/s183/daily_{per}.pkl")[["d", "s", "qv", "sqv", "krv", "krv_upbit"]]
    P = P[P.krv_upbit.fillna(0) > 0].copy()
    P["share"] = P.krv / (P.krv + P.qv.fillna(0) + P.sqv.fillna(0))
    P = P[P.share >= 0.20]
    rows = []
    for s, g in P.groupby("s"):
        if s not in K:
            continue
        a = K[s]
        t = a["t"].astype(np.int64)
        qv = a["qv"].astype(float)
        lo, hi = FB.live(s)
        if not np.isfinite(lo):
            continue
        o, h, l = (a[x].astype(float) for x in ("o", "h", "l"))
        days = g.d.values.astype(np.int64)
        # индексы свечей начала суток D и D−1
        i0 = np.searchsorted(t, days)
        ok = (i0 < len(t)) & (t[np.minimum(i0, len(t) - 1)] == days) & (i0 >= 96)
        days, i0, shr = days[ok], i0[ok], g.share.values[ok]
        res = []
        for D, i, sh in zip(days, i0, shr):
            if i + 96 >= len(t) or t[i + 96] != D + DAY or t[i - 96] != D - DAY:
                continue
            if D < lo + DAY or D + DAY > hi:
                continue
            ph, pl = h[i - 96:i].max(), l[i - 96:i].min()
            if not (np.all(qv[i - 96:i] >= 0)):
                continue
            target = o[i] + 0.5 * (ph - pl)
            mx_full = h[i:i + 95].max()                  # свечи 00:00 … 23:30 (последняя закрыта к 23:45)
            res.append((D, i, sh, target, mx_full, o[i]))
        if not res:
            continue
        R = pd.DataFrame(res, columns=["D", "i0", "share", "target", "mx", "open"])
        R["brk"] = R.mx > R.target
        R["dose"] = R.mx / R.target - 1
        Ie = R.i0.values + 94                            # свеча 23:30–23:45 → вход в её закрытие (23:45)
        Ib = R.i0.values + 91                            # свеча 22:45–23:00 → вход в 23:00 (вариант б)
        for col, I in (("net", Ie), ("net_b", Ib)):
            okt, net, stp, bars, tend = FB.trades(s, I, 0.25, 0.5, -1)
            R[col] = np.where(okt, net, np.nan)
        R["s"] = s
        rows.append(R)
    X = pd.concat(rows, ignore_index=True)
    X["t"] = X.D + DAY - 15 * 60
    X["per"] = per
    X.to_pickle(f"{OUT}/s190_g2_{per}.pkl")
    print(per, "монето-суток", len(X), "с пробоем", int(X.brk.sum()), flush=True)


def report():
    import common182 as C  # noqa: E402
    print("Г2 — шорт 23:45 → 00:15 UTC у монет с пробоем цели ботов Upbit (доля Кореи ≥ 20%) против тех же без пробоя\n")
    parts, parts_g = [], []
    for per in C.PER:
        X = pd.read_pickle(f"{OUT}/s190_g2_{per}.pkl")
        X = X[X.net.notna()]
        e, c = X[X.brk], X[~X.brk]
        d, se = C.diff(X.net, X.brk, X.t)
        parts.append((d, se, len(e)))
        m, t, n = C.ct(e.net, e.t); mc, tc, nc = C.ct(c.net, c.t)
        mo = C.months(per)
        print(f"{per}: пробой n={n} ({n / mo:.0f}/мес) {m:+.3%} (t {t:+.1f}), валовой ход шорта {m + 0.001:+.3%} | "
              f"без пробоя n={nc} {mc:+.3%} (t {tc:+.1f}) | Δ = {d:+.3%} (t {d / se:+.1f})")
        y = X[X.net_b.notna()]
        db, seb = C.diff(y.net_b, y.brk, y.t)
        print(f"    (б) на 30 мин раньше (23:00 → 23:30): пробой {y[y.brk].net_b.mean():+.3%}, без пробоя "
              f"{y[~y.brk].net_b.mean():+.3%}, Δ {db:+.3%} (t {db / seb:+.1f})")
        wk = pd.to_datetime(X.D, unit="s").dt.weekday >= 5
        for nm, msk in (("выходные", wk), ("будни", ~wk)):
            z = X[msk]
            dd, ss = C.diff(z.net, z.brk, z.t)
            print(f"    {nm}: Δ {dd:+.3%} (t {dd / ss:+.1f})")
        print("    доза (сила пробоя < 2% / 2–5% / ≥ 5%): " + " / ".join(
            f"{e[(e.dose >= a) & (e.dose < b)].net.mean():+.3%} ({int(((e.dose >= a) & (e.dose < b)).sum())})"
            for a, b in ((0, 0.02), (0.02, 0.05), (0.05, 99))))
        cut = C.ts(C.PER[per][2])
        print(f"    половины пробоя: {e[e.t < cut].net.mean():+.3%} / {e[e.t >= cut].net.mean():+.3%}")
    m, t = C.combine(parts)
    print(f"\nвместе: Δ = {m:+.3%} (t {t:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
