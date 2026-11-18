"""s143 — последние 48 ч перед разлоком (гипотеза — ВЫВОДЫ.md, записана до расчёта). События — s142/any_test.events()
(разовые разлоки всех получателей, кроме казны, ≥ 1% за сутки). W1: шорт T − 48 ч → T, стоп +25%; W2: T − 24 ч → T + 24 ч;
W3: T → T + 24 ч. Хедж — индекс альтов s103 на фактический срок; плацебо — та же монета за 45/90/135 сут.
Запуск в папке периода: MC_K=… MC_F=… MC_CUT=… python3 <repo>/research/s143/w48_test.py <период>;
сводка из /home/user/mc_data: python3 … report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s139", "s141", "s142"):
    sys.path.insert(0, os.path.join(HERE, "..", p))

DAY, H, OUT = 86400, 3600, "/home/user/mc_data"
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01"), "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-19", "2025-12-01")}
WIN = {"W1": (-48, 48), "W2": (-24, 48), "W3": (0, 24)}          # (вход относительно T, срок), часы


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def run(per):
    from common import K, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    import any_test  # noqa: E402
    t0, t1, _ = PER[per]
    T, I = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T, a - 900, "right")) - 1; j = int(np.searchsorted(T, b - 900, "right")) - 1
        return I[j] / I[i] - 1 if 0 <= i <= j < len(I) else np.nan

    E = any_test.events(); E = E[(E["T"] >= ts(t0)) & (E["T"] < ts(t1))]
    rows, last = [], {}
    for r in E.itertuples():
        if r.key not in K:
            continue
        lo, hi = live(r.key)
        if lo + 8 * DAY > r.T or r.T < last.get(r.key, -1) or r.T + 2 * DAY > hi:
            continue
        last[r.key] = r.T + 7 * DAY
        for w, (off, hold) in WIN.items():
            te = r.T + off * H
            i = idx_at(r.key, te)
            x = trade(r.key, i, tp=None, sl=0.25, hold_h=hold, side=-1) if i is not None else None
            if not x:
                continue
            t_end = int(K[r.key]["t"][i]) + 900 + int(x["bars"]) * 900
            pl = []
            for dd in (45, 90, 135):
                j = idx_at(r.key, te - dd * DAY)
                y = trade(r.key, j, tp=None, sl=0.25, hold_h=hold, side=-1) if j is not None else None
                if y:
                    pl.append(y["net"])
            rows.append(dict(w=w, s=r.key, slug=r.slug, T=r.T, t=te, share=r.share, ins=r.ins, net=x["net"], why=x["why"],
                             hed=x["net"] + mv(te, t_end), pl=np.mean(pl) if pl else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s143_{per}.pkl")
    print(per, "событий", len(E), "сделок", X.groupby("w").size().to_dict())


def report():
    from oi_test import ct  # noqa: E402
    A = []
    for per, (t0, t1, cut) in PER.items():
        X = pd.read_pickle(f"{OUT}/s143_{per}.pkl"); X["per"] = per; A.append(X)
        months = (ts(t1) - ts(t0)) / (30.4 * DAY); c = ts(cut)
        print(f"\n{per}:")
        sets = [(w, X[X.w == w]) for w in WIN] + [("W1 команде и инвесторам", X[(X.w == "W1") & (X.ins >= 0.01)])]
        for lab, x in sets:
            if len(x) < 8:
                print(f"  {lab:24s} n={len(x)}"); continue
            m, t, n = ct(x.net, x.t); mh, th, _ = ct(x.hed.dropna(), x.t[x.hed.notna()])
            dp = (x.net - x.pl).dropna(); md, td, _ = ct(dp, x.t[(x.net - x.pl).notna()]) if len(dp) >= 8 else (np.nan, np.nan, 0)
            print(f"  {lab:24s} n={n:4d} ({n / months:4.1f}/мес) шорт {m:+.2%} (t {t:+.1f}) в плюсе {(x.net > 0).mean():.0%} | "
                  f"половины {x[x.t < c].net.mean():+.2%} / {x[x.t >= c].net.mean():+.2%} | с хеджем {mh:+.2%} (t {th:+.1f}) | "
                  f"сверх плацебо {md:+.2%} (t {td:+.1f}) | стопов {(x.why == 'стоп').mean():.0%}")
    A = pd.concat(A, ignore_index=True)
    print("\nшесть лет:")
    for w in WIN:
        x = A[A.w == w]; m, t, n = ct(x.net, x.t); mh, th, _ = ct(x.hed.dropna(), x.t[x.hed.notna()])
        print(f"  {w}: n={n} шорт {m:+.2%} (t {t:+.1f}), с хеджем {mh:+.2%} (t {th:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
