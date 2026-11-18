"""s147 — отлив после начисления Binance при разрыве фандинга с Gate, KuCoin, HL (гипотеза — ВЫВОДЫ.md, записана до расчёта).
Событие — начисление Binance ≤ −0,3% (прошлое 4–8 ч назад, следующее не раньше T + 2 ч 15 мин). Разрыв площадки — сумма её
начислений в (T − интервал, T] минус ставка Binance; площадка «есть», если у неё есть начисления в ±24 ч от T (данные —
gap_fetch.py). Группы: A — наибольший разрыв ≥ 0,5 п. п., B — площадка есть, разрыв меньше, C — площадок нет. Шорт как у 🌊:
вход на закрытии свечи, кончающейся в T + 15 мин, 2 ч, стоп 15%; хедж — индекс альтов s103 на фактический срок; плацебо —
та же монета за 45/90/135 сут. Запуск в папке периода: MC_K=… MC_F=… MC_CUT=… python3 <repo>/research/s147/gap_test.py <период>;
сводка из /home/user/mc_data: python3 … report"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s141", "s147"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
import gap_fetch as G  # noqa: E402

DAY, OUT = 86400, "/home/user/mc_data"
CUT = {"2020–2022": "2021-10-01", "2022–2024": "2023-10-01", "2024–2026": "2025-12-01"}
SKIP = {"BTC", "ETH", "USDC", "FDUSD", "BUSD", "TUSD", "USDP", "DAI", "EUR", "BTCDOM", "DEFI", "FOOTBALL", "BLUEBIRD"}
VEN = ("gate", "kucoin", "hl")


def venues():
    out = {}
    for v in VEN:
        st = pickle.load(open(f"{OUT}/s147/{v}.pkl", "rb"))
        out[v] = {s: np.array(sorted(d.items()), float) for s, d in st["rows"].items() if d}
    return out


def run(per):
    from common import K, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    a0, a1, _ = G.PER[per]
    T_, I_ = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T_, a - 900, "right")) - 1; j = int(np.searchsorted(T_, b - 900, "right")) - 1
        return I_[j] / I_[i] - 1 if 0 <= i <= j < len(I_) else np.nan

    def deal(s, te):
        i = idx_at(s, te)
        x = trade(s, i, tp=None, sl=0.15, hold_h=2, side=-1) if i is not None else None
        if not x:
            return None, np.nan
        t_end = int(K[s]["t"][i]) + 900 + int(x["bars"]) * 900
        return x, x["net"] + mv(te, t_end)

    V, BF = venues(), G.binance_funding(per)
    rows = []
    for s in K:
        if s in SKIP or s not in BF:
            continue
        lo, hi = live(s)
        if not np.isfinite(lo):
            continue
        for T, r, I in G.events(BF[s], G.ts(a0), G.ts(a1)):
            te = T + 900
            if te < lo + DAY:
                continue
            gaps = {}
            for v in VEN:
                a = V[v].get(s)
                if a is None or not np.any(np.abs(a[:, 0] - T) <= DAY):
                    continue
                w = a[(a[:, 0] > T - I + 60) & (a[:, 0] <= T + 60), 1]
                gaps[v] = float(w.sum()) - r
            x, h = deal(s, te)
            if not x:
                continue
            pl = [z["net"] for z in (deal(s, te - dd * DAY)[0] for dd in (45, 90, 135)) if z]
            g = max(gaps.values()) if gaps else np.nan
            rows.append(dict(s=s, t=te, r=r, I=I // 3600, gap=g, grp="A" if g >= 0.005 else ("B" if gaps else "C"),
                             **{f"g_{v}": gaps.get(v, np.nan) for v in VEN}, net=x["net"], why=x["why"], hed=h,
                             pl=np.mean(pl) if pl else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s147_{per}.pkl")
    print(per, "событий", len(X), X.groupby("grp").size().to_dict())


def diff(a, b, col="net"):
    da = a.groupby(pd.to_datetime(a.t, unit="s").dt.date)[col].mean()
    db = b.groupby(pd.to_datetime(b.t, unit="s").dt.date)[col].mean()
    d = a[col].mean() - b[col].mean(); se = np.sqrt(da.var() / len(da) + db.var() / len(db))
    return d, d / se if se > 0 else np.nan


def line(x, months, c, ct):
    if len(x) < 8:
        return f"n={len(x)}" + (f" {x.net.mean():+.2%}" if len(x) else "")
    m, t, n = ct(x.net, x.t); mh, th, _ = ct(x.hed.dropna(), x.t[x.hed.notna()])
    dp = (x.net - x.pl).dropna()
    md, td, _ = ct(dp, x.t[(x.net - x.pl).notna()]) if len(dp) >= 8 else (np.nan, np.nan, 0)
    return (f"n={n:4d} ({n / months:5.1f}/мес) {m:+.2%} (t {t:+.1f}) | половины {x[x.t < c].net.mean():+.2%} / "
            f"{x[x.t >= c].net.mean():+.2%} | с хеджем {mh:+.2%} (t {th:+.1f}) | сверх плацебо {md:+.2%} (t {td:+.1f}) | "
            f"в плюсе {(x.net > 0).mean():.0%}")


def report():
    from oi_test import ct  # noqa: E402
    A = []
    for per, (a0, a1, _) in G.PER.items():
        X = pd.read_pickle(f"{OUT}/s147_{per}.pkl"); X["per"] = per; A.append(X)
        months = (G.ts(a1) - G.ts(a0)) / (30.4 * DAY); c = G.ts(CUT[per])
        print(f"\n{per}: событий {len(X)}, площадки: " + ", ".join(f"{v} {X[f'g_{v}'].notna().mean():.0%}" for v in VEN)
              + f"; медиана разрыва {X.gap.median():+.2%}")
        for g in ("A", "B", "C"):
            print(f"  {g}: " + line(X[X.grp == g], months, c, ct))
        d, td = diff(X[X.grp == "A"], X[X.grp == "B"]) if (X.grp == "A").sum() >= 8 else (np.nan, np.nan)
        print(f"  A − B: {d:+.2%} (t {td:+.1f})")
        print("  A ≥ 0,3 п. п.: " + line(X[X.gap >= 0.003], months, c, ct))
        print("  A, ставка −0,3…−1%: " + line(X[(X.grp == "A") & (X.r > -0.01)], months, c, ct))
        print("  A, ставка ≤ −1%: " + line(X[(X.grp == "A") & (X.r <= -0.01)], months, c, ct))
        print("  B+C, ставка ≤ −1%: " + line(X[(X.grp != "A") & (X.r <= -0.01)], months, c, ct))
        for v in VEN:
            print(f"  разрыв {v} ≥ 0,5: " + line(X[X[f"g_{v}"] >= 0.005], months, c, ct))
    A = pd.concat(A, ignore_index=True)
    a, b = A[A.grp == "A"], A[A.grp == "B"]
    m, t, n = ct(a.net, a.t); mh, th, _ = ct(a.hed.dropna(), a.t[a.hed.notna()]); d, td = diff(a, b)
    print(f"\nшесть лет: A n={n} {m:+.2%} (t {t:+.1f}), с хеджем {mh:+.2%} (t {th:+.1f}); B {b.net.mean():+.2%}; "
          f"A − B {d:+.2%} (t {td:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
