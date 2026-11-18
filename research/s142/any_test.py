"""s142 — любой разовый разлок ≥ 1% (гипотеза — ВЫВОДЫ.md, записана до расчёта). События — s139/unlock_test.events()
(разлоки одним куском по группам «инсайдеры» и «сообщество», без noncirculating и burned), сложенные по суткам UTC проекта.
U6 — сумма ≥ 1%; U6с — сумма ≥ 1%, но инсайдерам < 1% (вне 🔑). Шорт за 7 сут до T, выход через сутки после (192 ч),
стоп +50%; хедж — индекс альтов s103 на фактический срок сделки; плацебо — та же монета за 45/90/135 сут.
Запуск в папке периода: MC_K=… MC_F=… MC_CUT=… python3 <repo>/research/s142/any_test.py <период>;
сводка из /home/user/mc_data: python3 … report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s139", "s141"):
    sys.path.insert(0, os.path.join(HERE, "..", p))

DAY, OUT = 86400, "/home/user/mc_data"
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01"), "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-19", "2025-12-01")}


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def events():
    import unlock_test as U  # noqa: E402
    E = U.events()
    E["day"] = E["T"] // DAY
    g = E.groupby(["slug", "key", "day"])
    A = g.agg(T=("T", "min"), share=("share", "sum")).reset_index()
    ins = E[E.grp == "инсайдеры"].groupby(["slug", "day"]).share.sum().rename("ins")
    A = A.merge(ins, on=["slug", "day"], how="left").fillna({"ins": 0.0})
    return A[A.share >= 0.01].sort_values("T").reset_index(drop=True)


def run(per):
    from common import K, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    t0, t1, _ = PER[per]
    T, I = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T, a - 900, "right")) - 1; j = int(np.searchsorted(T, b - 900, "right")) - 1
        return I[j] / I[i] - 1 if 0 <= i <= j < len(I) else np.nan

    E = events(); E = E[(E["T"] >= ts(t0)) & (E["T"] < ts(t1))]
    rows, last = [], {}
    for r in E.itertuples():
        if r.key not in K:
            continue
        lo, hi = live(r.key); te = r.T - 7 * DAY
        if lo + DAY > te or te < last.get(r.key, -1):
            continue
        i = idx_at(r.key, te)
        x = trade(r.key, i, tp=None, sl=0.5, hold_h=192, side=-1) if i is not None else None
        if not x:
            continue
        last[r.key] = te + 7 * DAY
        t_end = int(K[r.key]["t"][i]) + 900 + int(x["bars"]) * 900
        pl = []
        for dd in (45, 90, 135):
            j = idx_at(r.key, te - dd * DAY)
            y = trade(r.key, j, tp=None, sl=0.5, hold_h=192, side=-1) if j is not None else None
            if y:
                pl.append(y["net"])
        rows.append(dict(s=r.key, slug=r.slug, T=r.T, t=te, share=r.share, ins=r.ins, net=x["net"], why=x["why"],
                         hed=x["net"] + mv(te, t_end), pl=np.mean(pl) if pl else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s142_{per}.pkl")
    print(per, "событий", len(E), "сделок", len(X), "из них вне 🔑", int((X.ins < 0.01).sum()))


def report():
    from oi_test import ct  # noqa: E402
    A = []
    for per, (t0, t1, cut) in PER.items():
        X = pd.read_pickle(f"{OUT}/s142_{per}.pkl"); X["per"] = per; A.append(X)
        months = (ts(t1) - ts(t0)) / (30.4 * DAY); c = ts(cut)
        print(f"\n{per}:")
        for lab, x in (("U6 любой ≥ 1%", X), ("U6с вне 🔑", X[X.ins < 0.01])):
            if len(x) < 8:
                print(f"  {lab:16s} n={len(x)}"); continue
            m, t, n = ct(x.net, x.t); mh, th, _ = ct(x.hed.dropna(), x.t[x.hed.notna()])
            dp = (x.net - x.pl).dropna(); md, td, _ = ct(dp, x.t[(x.net - x.pl).notna()]) if len(dp) >= 8 else (np.nan, np.nan, 0)
            print(f"  {lab:16s} n={n:4d} ({n / months:4.1f}/мес) шорт {m:+.2%} (t {t:+.1f}) | половины {x[x.t < c].net.mean():+.2%} / "
                  f"{x[x.t >= c].net.mean():+.2%} | с хеджем {mh:+.2%} (t {th:+.1f}) | сверх плацебо {md:+.2%} (t {td:+.1f})")
    A = pd.concat(A, ignore_index=True)
    print("\nшесть лет:")
    for lab, x in (("U6", A), ("U6с", A[A.ins < 0.01])):
        m, t, n = ct(x.net, x.t); mh, th, _ = ct(x.hed.dropna(), x.t[x.hed.notna()])
        print(f"  {lab}: n={n} шорт {m:+.2%} (t {t:+.1f}), с хеджем {mh:+.2%} (t {th:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
