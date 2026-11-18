"""s145 — скачок ≥ 5% за час 00–01 UTC у монет без рынка к воне с хеджем индексом альтов (гипотеза — ВЫВОДЫ.md, записана до
расчёта). События — как в s135 (часовые свечи из 15-мин, рынок к воне — строки s15/kr_panel.pkl папки периода); сделка
пересчитана s15/common.trade на 15-мин свечах (вход на закрытии свечи, закрывающей час), 10/25/48; хедж — индекс альтов s103
на фактический срок. Запуск в папке периода: MC_K=… MC_F=… MC_CUT=… python3 <repo>/research/s145/reset_hedge.py <период>;
сводка из /home/user/mc_data: python3 … report"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s135", "s141"):
    sys.path.insert(0, os.path.join(HERE, "..", p))

DAY, H1, OUT = 86400, 3600, "/home/user/mc_data"
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01"), "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-17", "2025-12-01")}


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def run(per):
    from common import K, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    import reset_test as R  # noqa: E402
    t0, t1, _ = PER[per]
    T, I = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T, a - 900, "right")) - 1; j = int(np.searchsorted(T, b - 900, "right")) - 1
        return I[j] / I[i] - 1 if 0 <= i <= j < len(I) else np.nan

    P = pickle.load(open("s15/kr_panel.pkl", "rb"))
    kor = {s: set((d["T"].values.astype(np.int64) - H1).tolist()) for s, d in P.items()}
    rows = []
    for s in K:
        if s in R.SKIP:
            continue
        lo, hi = live(s)
        if not np.isfinite(lo):
            continue
        a = R.hourly(K[s]); t = a["t"]
        r1 = np.r_[np.nan, a["c"][1:] / a["c"][:-1] - 1]
        ok = (t >= lo + DAY) & (t + H1 <= hi) & (a["qv"] > 0) & (t >= ts(t0) - H1) & (t < ts(t1))
        ks, last = kor.get(s, set()), -10 ** 18
        for i in np.flatnonzero(ok & (r1 >= 0.05)):
            H = int(t[i])
            if H in ks:
                continue
            open0 = H % DAY == 0
            if not open0:
                if H - last < DAY:
                    continue
                last = H
            te = H + H1                                            # закрытие часа
            j = idx_at(s, te)
            x = trade(s, j, tp=0.10, sl=0.25, hold_h=48, side=-1) if j is not None else None
            if not x:
                continue
            t_end = int(K[s]["t"][j]) + 900 + int(x["bars"]) * 900
            pl = []
            if open0:
                for dd in (45, 90, 135):
                    jj = idx_at(s, te - dd * DAY)
                    y = trade(s, jj, tp=0.10, sl=0.25, hold_h=48, side=-1) if jj is not None else None
                    if y:
                        pl.append(y["net"])
            rows.append(dict(s=s, t=te, open0=open0, r1=float(r1[i]), net=x["net"], hed=x["net"] + mv(te, t_end),
                             why=x["why"], pl=np.mean(pl) if pl else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s145_{per}.pkl")
    print(per, "событий", len(X), "из них в 00–01 UTC", int(X.open0.sum()))


def diff(a, b, col):
    da = a.groupby(pd.to_datetime(a.t, unit="s").dt.date)[col].mean()
    db = b.groupby(pd.to_datetime(b.t, unit="s").dt.date)[col].mean()
    d = a[col].mean() - b[col].mean(); se = np.sqrt(da.var() / len(da) + db.var() / len(db))
    return d, d / se if se > 0 else np.nan


def report():
    from oi_test import ct  # noqa: E402
    A = []
    for per, (t0, t1, cut) in PER.items():
        X = pd.read_pickle(f"{OUT}/s145_{per}.pkl"); X["per"] = per; A.append(X)
        months = (ts(t1) - ts(t0)) / (30.4 * DAY); c = ts(cut)
        o, r = X[X.open0], X[~X.open0]
        m, t, n = ct(o.net, o.t); mh, th, _ = ct(o.hed.dropna(), o.t[o.hed.notna()])
        rh, rth, _ = ct(r.hed.dropna(), r.t[r.hed.notna()]); d, td = diff(o, r, "hed")
        dp = (o.net - o.pl).dropna(); md, tdp, _ = ct(dp, o.t[(o.net - o.pl).notna()])
        print(f"{per}: 00–01 UTC n={n} ({n / months:.1f}/мес) шорт {m:+.2%} (t {t:+.1f}) | с хеджем {mh:+.2%} (t {th:+.1f}) | "
              f"половины с хеджем {o[o.t < c].hed.mean():+.2%} / {o[o.t >= c].hed.mean():+.2%} | сверх плацебо {md:+.2%} (t {tdp:+.1f})"
              f"\n           другие часы n={len(r)} с хеджем {rh:+.2%} (t {rth:+.1f}) | разница с хеджем {d:+.2%} (t {td:+.1f})")
    A = pd.concat(A, ignore_index=True)
    o, r = A[A.open0], A[~A.open0]
    m, t, n = ct(o.net, o.t); mh, th, _ = ct(o.hed.dropna(), o.t[o.hed.notna()]); d, td = diff(o, r, "hed")
    print(f"шесть лет: 00–01 UTC n={n} шорт {m:+.2%} (t {t:+.1f}), с хеджем {mh:+.2%} (t {th:+.1f}); "
          f"разница с другими часами с хеджем {d:+.2%} (t {td:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
