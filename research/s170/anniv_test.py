"""s170 — шорт за 48 ч до месячной годовщины запуска фьючерса (k = 1…12; гипотеза — ВЫВОДЫ.md, записана до расчёта).
Запуск — первая 15-мин свеча с оборотом; годовщина — тот же день месяца и время суток (нет дня — последний день месяца).
Плацебо — та же монета и k со сдвигом годовщины на ±15 сут. Запуск в папке периода с MC_K/MC_F/MC_CUT:
python3 <repo>/research/s170/anniv_test.py <период>; сводка из /home/user/mc_data: python3 … report"""
import calendar
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s141"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
OUT, DAY, H = "/home/user/mc_data", 86400, 3600
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01"), "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-17", "2025-12-01")}


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def add_months(t0, k):
    d = pd.Timestamp(t0, unit="s", tz="UTC")
    y, m = divmod(d.month - 1 + k, 12); y += d.year; m += 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return int(d.replace(year=y, month=m, day=day).timestamp())


def run(per):
    from common import K, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    t0, t1 = ts(PER[per][0]), ts(PER[per][1])
    T_, I_ = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T_, a - 900, "right")) - 1; j = int(np.searchsorted(T_, b - 900, "right")) - 1
        return I_[j] / I_[i] - 1 if 0 <= i <= j < len(I_) else np.nan

    U = pd.concat([pd.read_pickle(f"{OUT}/s142_{p}.pkl") for p in PER])
    UT = {s: np.sort(g["T"].values.astype(np.int64)) for s, g in U.groupby("s")}

    def short(s, te, hold=48):
        i = idx_at(s, te)
        if i is None or int(K[s]["t"][i]) + 900 != te:
            return None
        return trade(s, i, tp=None, sl=0.25, hold_h=hold, side=-1)

    rows = []
    for s in K:
        lo, hi = live(s)
        if not np.isfinite(lo) or lo < t0 + 3 * DAY or lo >= t1:
            continue
        for k in range(1, 13):
            A = add_months(int(lo), k)
            if A >= t1 or A + 2 * DAY > hi:
                break
            x = short(s, A - 2 * DAY)
            if not x:
                continue
            y = short(s, A)
            pl = [z["net"] for z in (short(s, A + d * DAY - 2 * DAY) for d in (-15, 15)) if z]
            t_end = A - 2 * DAY + int(x["bars"]) * 900
            u = UT.get(s)
            rows.append(dict(s=s, k=k, A=A, t=A - 2 * DAY, net=x["net"], why=x["why"], post=y["net"] if y else np.nan,
                             pl=np.mean(pl) if pl else np.nan, hed=x["net"] + mv(A - 2 * DAY, t_end),
                             unl=bool(u is not None and np.any(np.abs(u - A) <= 3 * DAY))))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s170_{per}.pkl")
    print(per, "событий", len(X), "монет", X.s.nunique() if len(X) else 0, flush=True)


def report():
    from oi_test import ct  # noqa: E402
    A = []
    for per, (a, b, cut) in PER.items():
        X = pd.read_pickle(f"{OUT}/s170_{per}.pkl"); X["per"] = per; A.append(X)
        months = (ts(b) - ts(a)) / (30.4 * DAY); c = ts(cut)
        m, t, n = ct(X.net, X.t); mh, th, _ = ct(X.hed.dropna(), X.t[X.hed.notna()])
        d = (X.net - X.pl).dropna(); md, td, _ = ct(d, X.t[(X.net - X.pl).notna()])
        mp, tp, _ = ct(X.post.dropna(), X.t[X.post.notna()])
        print(f"\n{per}: n={n} ({n / months:.1f}/мес) шорт за 48 ч до годовщины {m:+.2%} (t {t:+.1f}) | половины {X[X.t < c].net.mean():+.2%} / "
              f"{X[X.t >= c].net.mean():+.2%} | плацебо ±15 сут {X.pl.mean():+.2%} | разница {md:+.2%} (t {td:+.1f}) | с хеджем {mh:+.2%} "
              f"(t {th:+.1f}) | после годовщины 48 ч {mp:+.2%} (t {tp:+.1f})")
        for nm, x in (("k 1–3", X[X.k <= 3]), ("k 4–6", X[(X.k >= 4) & (X.k <= 6)]), ("k 7–12", X[X.k >= 7]), ("без разлоков 🔑⁺ ±3 сут", X[~X.unl])):
            if len(x) >= 8:
                dd = (x.net - x.pl).dropna(); mdd, tdd, _ = ct(dd, x.t[(x.net - x.pl).notna()])
                print(f"   {nm:24s} n={len(x):4d} {x.net.mean():+.2%} | плацебо {x.pl.mean():+.2%} | разница {mdd:+.2%} (t {tdd:+.1f})")
    A = pd.concat(A, ignore_index=True)
    m, t, n = ct(A.net, A.t); d = (A.net - A.pl).dropna(); md, td, _ = ct(d, A.t[(A.net - A.pl).notna()])
    print(f"\nшесть лет: n={n} {m:+.2%} (t {t:+.1f}) | разница с плацебо {md:+.2%} (t {td:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
