"""s265 — Г2 s263: сильный день перпа на акцию США → откат за ночь (ребаланс плечевых ETF к закрытию по ходу дня, Cheng и
Madhavan 2009). Правило и порог — ВЫВОДЫ.md (записаны до расчёта доходов). Ход дня r = цена перпа в 16:00 ET к цене в 9:45 ET
(перп в часы торгов идёт с индексом, s263). |r| ≥ 3% → против хода: вход в 16:15 ET, выход в 9:30 ET следующего торгового
дня, стоп 5%. Только пн–чт, следующий день — полный торговый (через выходные — другая механика, s74). Общее — s264/tradfi.py.
Запуск из /home/user/mc_data: python3 -I <repo>/research/s265/run.py [count|main]"""
import datetime
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s264"))
import tradfi as T  # noqa: E402

TH = 0.03


def events():
    U = T.universe()
    days = T.trading_days()
    dset = set(days)
    rows = []
    for s, grp in U.items():
        S = T.Sym(s)
        for d in days:
            nd = d + datetime.timedelta(1)
            if d.weekday() > 3 or nd not in dset:
                continue
            r = S.px(T.ts(d, 16, 0)) / S.px(T.ts(d, 9, 45)) - 1
            if not (abs(r) >= TH):
                continue
            Te, Tx = T.ts(d, 16, 15), T.ts(nd, 9, 30)
            k = S.idx(Te)
            if not S.ok(k):
                continue
            rows.append(dict(s=s, grp=grp, d=d, i=k, n=(Tx - Te) // T.BAR, te=Te, side=-1 if r > 0 else 1, mag=abs(r), r=r))
    return pd.DataFrame(rows)


def count():
    E = events()
    mo = T.months(E)
    mid = float(np.median(E.te))
    print(f"всего: {len(E)} событий ({len(E) / mo:.1f} в месяц), бумаг {E.s.nunique()}, дней {E.d.nunique()}; середина "
          f"{pd.Timestamp(mid, unit='s').date()}; 2-я половина {(E.te >= mid).sum() / ((E.te.max() - mid) / T.MONTH):.1f} в месяц")
    print("рост → шорт / падение → лонг:", (E.side == -1).sum(), "/", (E.side == 1).sum(), "; по группам", E.grp.value_counts().to_dict())
    print("по месяцам:", E.groupby(pd.to_datetime(E.te, unit="s").dt.strftime("%Y-%m")).size().to_dict())


def main():
    E = events()
    X = T.trades(E)
    X.to_pickle("s265_trades.pkl")
    T.report(X, "Г2: день США |r| ≥ 3% → против хода 16:15 → 9:30 ET")
    for side, nm in ((-1, "рост → шорт"), (1, "падение → лонг")):
        x = X[X.side == side]
        print(f"  {nm}: {T.line(x, T.months(X))}")


if __name__ == "__main__":
    {"count": count, "main": main}[sys.argv[1] if len(sys.argv) > 1 else "count"]()
