"""s28 — устойчивость шорта T − 7 сут → T + 1 сут перед разлоками ≥ 2% и ≥ 5% монет в обращении (unlock_study.build):
стопы (25%, 50%, 100%, нет), хвосты, кварталы, размер, получатели, cliff/linear, и «разлок случился» — рост монет в
обращении по данным CoinMarketCap за T − 3 … T + 5 сут. Запуск из папки с данными."""
import os
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from unlock_study import CUT, DAY, H, build, ct, hist, px_ok      # noqa: E402
from unlock_trades import run                                    # noqa: E402


def realized(r):
    h = hist(r.cid)
    if h is None:
        return np.nan
    a = h[h.t <= r.t - 3 * DAY]; b = h[h.t <= r.t + 5 * DAY]
    if not len(a) or not len(b) or not a.circ.iloc[-1]:
        return np.nan
    return (b.circ.iloc[-1] / a.circ.iloc[-1] - 1) * 100


def line(x, label):
    m, t, n = ct(x.net.values, x.t.values)
    if not n:
        return
    q = x.net.quantile([0.05, 0.5]).values
    print(f"  {label:34s} n={n:4d} {m*100:+6.2f}% (t {t:+4.1f}) медиана {q[1]*100:+5.1f}% в плюсе {(x.net>0).mean():.0%} "
          f"5%-хвост {q[0]*100:+6.1f}% худшая {x.net.min()*100:+6.0f}% стопов {(x.why=='стоп').mean():.0%} фандинг {x.fund.mean()*100:+.2f}%")


if __name__ == "__main__":
    E = build()
    E = E[E["size"] >= 2].copy()
    E = E[[px_ok(r) for r in E.itertuples()]].sort_values("t")
    E["real"] = [realized(r) for r in E.itertuples()]
    E["first"] = ~E.duplicated("s") & (E["size"] >= 5)
    rows = []
    for r in E.itertuples():
        for sl in (None, 0.25, 0.5, 1.0):
            x = run(r.s, r.t - 7 * DAY, 8, sl)
            if x:
                rows.append(dict(s=r.s, t=r.t, size=r.size, team=r.team, cliff=r.cliff, real=r.real, first=r.first,
                                 usd=r.usd, sl=sl or 0, **x))
    R = pd.DataFrame(rows)
    R.to_pickle("s28/robust.pkl")
    for lo in (2, 5):
        X = R[R["size"] >= lo]
        print(f"\n=== разлоки ≥ {lo}%: шорт T − 7 → T + 1")
        for sl, x in X.groupby("sl"):
            line(x, f"стоп {'нет' if sl == 0 else f'{sl:.0%}'}")
        x = X[X.sl == 0.5]
        print("  — стоп 50% по частям:")
        x = x.assign(q=pd.to_datetime(x.t, unit="s").dt.to_period("Q").astype(str))
        for q, y in x.groupby("q"):
            line(y, f"квартал {q}")
        for a, b in ((2, 5), (5, 10), (10, 25), (25, 1e9)):
            line(x[(x["size"] >= a) & (x["size"] < b)], f"размер {a}–{b if b < 1e9 else '∞'}%")
        line(x[x.team >= 0.5], "команда и инвесторы ≥ 50%")
        line(x[x.team < 0.5], "прочие получатели")
        line(x[x.cliff], "есть cliff")
        line(x[~x.cliff], "только linear")
        line(x[x["first"]], "первый разлок монеты ≥ 5%")
        line(x[~x["first"]], "не первый")
        line(x[x.real >= 0.5 * x["size"]], "в обращении выросло ≥ половины разлока")
        line(x[x.real < 0.5 * x["size"]], "выросло меньше половины")
        line(x[x.real.isna()], "нет данных об обращении")
        line(x[x.usd >= 1e6], "разлок ≥ $1 млн")
        line(x[x.usd < 1e6], "разлок < $1 млн")
