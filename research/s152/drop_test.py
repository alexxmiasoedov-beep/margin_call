"""s152 — шорт после часового падения ликвидного альта к BTC (гипотеза — ВЫВОДЫ.md, записана до расчёта). События —
drop_events.py: топ-30 по обороту за 30 сут, ход к BTC за час ≤ порога (−1/−2/−3/−5%; основной −2%), по монете раз в 4 ч;
зеркало — рост к BTC ≥ +2%. Шорт на закрытии часа: 4 ч, стоп 5% (основная), 1 ч и 24 ч для отчёта; хедж BTC и индексом
альтов на фактический срок; плацебо — та же монета за 45/90/135 сут. Запуск в папке периода с MC_K/MC_F/MC_CUT:
python3 <repo>/research/s152/drop_test.py <период> <начало> <конец>; сводка из /home/user/mc_data: python3 … report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s141", "s135", "s152"):
    sys.path.insert(0, os.path.join(HERE, "..", p))

DAY, H1, OUT = 86400, 3600, "/home/user/mc_data"
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01"), "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-17", "2025-12-01")}


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def run(per):
    import drop_events as E  # noqa: E402
    from common import K, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    t0, t1 = ts(PER[per][0]), ts(PER[per][1])
    T_, I_ = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T_, a - 900, "right")) - 1; j = int(np.searchsorted(T_, b - 900, "right")) - 1
        return I_[j] / I_[i] - 1 if 0 <= i <= j < len(I_) else np.nan

    def btc(a, b):
        i, j = idx_at("BTC", a), idx_at("BTC", b)
        return float(K["BTC"]["c"][j] / K["BTC"]["c"][i] - 1) if i is not None and j is not None else np.nan

    H = E.hourly_all(); top = E.universe(H, t0, t1)
    ev = [(s, T, r, "drop") for s, T, r in E.events(H, top, t0, t1, -0.01)]
    # зеркало: рост к BTC ≥ +2% (тот же отбор, знак наоборот)
    b = H["BTC"]; bt = {int(t): c for t, c in zip(b["t"], b["c"])}
    for s, a in H.items():
        if s == "BTC":
            continue
        t, c = a["t"], a["c"]; last = -10 ** 18
        for i in range(1, len(t)):
            T = int(t[i])
            if not (t0 <= T < t1) or T - last < 4 * H1 or a["qv"][i] <= 0 or s not in top.get(T - T % DAY, ()):
                continue
            b0, b1 = bt.get(T - H1), bt.get(T)
            if b0 is None or b1 is None or t[i - 1] != T - H1:
                continue
            rel = (c[i] / c[i - 1] - 1) - (b1 / b0 - 1)
            if rel >= 0.02:
                ev.append((s, T + H1, rel, "rise")); last = T
    rows = []
    for s, te, rel, kind in ev:
        i = idx_at(s, te)
        if i is None or int(K[s]["t"][i]) + 900 != te:
            continue
        x = trade(s, i, tp=None, sl=0.05, hold_h=4, side=-1)
        if not x:
            continue
        t_end = int(K[s]["t"][i]) + 900 + int(x["bars"]) * 900
        y = trade(s, i, tp=None, sl=0.05, hold_h=1, side=-1)
        z = trade(s, i, tp=None, sl=0.05, hold_h=24, side=-1)
        pl = []
        if kind == "drop" and rel <= -0.02:
            for dd in (45, 90, 135):
                j = idx_at(s, te - dd * DAY)
                w = trade(s, j, tp=None, sl=0.05, hold_h=4, side=-1) if j is not None else None
                if w:
                    pl.append(w["net"])
        rows.append(dict(s=s, t=te, rel=rel, kind=kind, net=x["net"], why=x["why"], hb=x["net"] + btc(te, t_end),
                         ha=x["net"] + mv(te, t_end), n1=y["net"] if y else np.nan, n24=z["net"] if z else np.nan,
                         pl=np.mean(pl) if pl else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s152_{per}.pkl")
    print(per, "событий", X.groupby("kind").size().to_dict(), flush=True)


def report():
    from oi_test import ct  # noqa: E402
    A = []
    for per, (a, b, cut) in PER.items():
        X = pd.read_pickle(f"{OUT}/s152_{per}.pkl"); X["per"] = per; A.append(X)
        months = (ts(b) - ts(a)) / (30.4 * DAY); c = ts(cut)
        print(f"\n{per}:")
        for name, x in (("падение ≤ −2% (основная)", X[(X.kind == "drop") & (X.rel <= -0.02)]),
                        ("падение −1…−2%", X[(X.kind == "drop") & (X.rel > -0.02)]),
                        ("падение ≤ −3%", X[(X.kind == "drop") & (X.rel <= -0.03)]),
                        ("падение ≤ −5%", X[(X.kind == "drop") & (X.rel <= -0.05)]),
                        ("рост ≥ +2% (зеркало)", X[X.kind == "rise"])):
            m, t, n = ct(x.net, x.t); mb, tb, _ = ct(x.hb.dropna(), x.t[x.hb.notna()]); ma, ta, _ = ct(x.ha.dropna(), x.t[x.ha.notna()])
            m1, _, _ = ct(x.n1.dropna(), x.t[x.n1.notna()]); m24, t24, _ = ct(x.n24.dropna(), x.t[x.n24.notna()])
            dp = (x.net - x.pl).dropna()
            md, td, _ = ct(dp, x.t[(x.net - x.pl).notna()]) if len(dp) >= 8 else (np.nan, np.nan, 0)
            print(f"  {name:24s} n={n:6d} ({n / months:4.0f}/мес) 4 ч {m:+.3%} (t {t:+.1f}) | половины {x[x.t < c].net.mean():+.3%} / "
                  f"{x[x.t >= c].net.mean():+.3%} | хедж BTC {mb:+.3%} (t {tb:+.1f}) | хедж альтов {ma:+.3%} | 1 ч {m1:+.3%} | "
                  f"24 ч {m24:+.3%} (t {t24:+.1f}) | сверх плацебо {md:+.3%} (t {td:+.1f})")
    A = pd.concat(A, ignore_index=True); x = A[(A.kind == "drop") & (A.rel <= -0.02)]
    m, t, n = ct(x.net, x.t); mb, tb, _ = ct(x.hb.dropna(), x.t[x.hb.notna()])
    print(f"\nшесть лет, основная: n={n} 4 ч {m:+.3%} (t {t:+.1f}), хедж BTC {mb:+.3%} (t {tb:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
