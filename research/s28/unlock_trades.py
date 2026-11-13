"""s28 — сделки шорт вокруг разлоков (события — unlock_study.build, размер ≥ 1%, сверка цены): вход на закрытии 15-мин свечи
в момент T − 14 сут, T − 7 сут (выход T + 1 сут) и T (выход T + 7 сут), стоп +25% и без стопа, комиссия 0,1%, фактический
фандинг; «к рынку» — плюс медиана простой доходности всех фьючерсов за срок сделки. Плацебо — та же монета за 45, 90,
135 сут до разлока без разлоков в ±10 сут. Запуск из папки с данными (после cmc_fetch.py): python3 unlock_trades.py"""
import os
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from unlock_study import BAR, CUT, DAY, GR, K, build, ct, px_ok, trade      # noqa: E402

g = GR["grid"]; C = GR["C"]
PLANS = {"T−14→T+1": (-14, 15), "T−7→T+1": (-7, 8), "T→T+7": (0, 7)}


def mkt(t0, t1):
    k0, k1 = np.searchsorted(g, t0), np.searchsorted(g, t1)
    if k1 >= len(g) or k1 == k0:
        return 0.0 if k1 == k0 else np.nan
    with np.errstate(all="ignore"):
        return float(np.nanmedian(C[:, k1] / C[:, k0] - 1))


def run(s, t_entry, hold_d, sl):
    t = K[s]["t"]; i = int(np.searchsorted(t, t_entry, "right") - 1)
    if i < 0:
        return None
    r = trade(s, i, tp=None, sl=sl, hold_h=hold_d * 24, side=-1)
    if r is None:
        return None
    t0 = float(t[i]) + BAR
    r["mkt"] = r["net"] + mkt(t0, t0 + r["bars"] * BAR)
    return r


def table(R, label):
    print(f"\n{label}")
    for (plan, sl), x in R.groupby(["plan", "sl"], sort=False):
        m, t, n = ct(x.net.values, x.t.values)
        mm, tm, _ = ct(x.mkt.values, x.t.values)
        h1, h2 = x[x.t < CUT].net.mean(), x[x.t >= CUT].net.mean()
        print(f"  {plan:9s} стоп {'нет' if sl == 0 else f'{sl:.0%}':>4s}: n={n:4d} чистыми {m*100:+6.2f}% (t {t:+4.1f}, медиана "
              f"{x.net.median()*100:+5.1f}%, в плюсе {(x.net > 0).mean():.0%}, стопов {(x.why == 'стоп').mean():.0%}) "
              f"к рынку {mm*100:+6.2f}% (t {tm:+4.1f}) фандинг {x.fund.mean()*100:+5.2f}% половины {h1*100:+.2f}/{h2*100:+.2f}%")


def trades(E, shift_d=0):
    rows = []
    for r in E.itertuples():
        for plan, (a, hold) in PLANS.items():
            for sl in (0.25, None):
                x = run(r.s, r.t + (a - shift_d) * DAY, hold, sl)
                if x:
                    rows.append(dict(s=r.s, t=r.t - shift_d * DAY, plan=plan, sl=sl or 0, size=r.size, team=r.team, **x))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    E = build()
    E = E[E["size"] >= 1].copy()
    E = E[[px_ok(r) for r in E.itertuples()]]
    print(f"разлоков ≥ 1% после сверки цены: {len(E)}")
    R = trades(E)
    R.to_pickle("s28/trades.pkl")
    table(R, "=== все разлоки ≥ 1%")
    table(R[R["size"] >= 2], "=== разлоки ≥ 2%")
    table(R[R["size"] >= 5], "=== разлоки ≥ 5%")
    table(R[R.team >= 0.5], "=== команда и инвесторы ≥ половины")
    E = E.sort_values("t")
    first = E[E["size"] >= 5].groupby("s").head(1)
    table(R[R.t.isin(set(first.t)) & R.s.isin(set(first.s))].merge(first[["s", "t"]], on=["s", "t"]),
          "=== первый разлок монеты ≥ 5%")
    allt = {s: E[E.s == s].t.values for s in E.s.unique()}
    P = []
    for back in (45, 90, 135):
        Q = E[[not np.any(np.abs(allt[r.s] - (r.t - back * DAY)) < 10 * DAY) for r in E.itertuples()]]
        P.append(trades(Q, shift_d=back))
    table(pd.concat(P, ignore_index=True), "--- плацебо (та же монета за 45–135 сут)")
