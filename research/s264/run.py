"""s264 — Г3 s263: разрыв перпа на акцию США к открытию → откат днём (Berkman, Koch, Tuttle, Zhang 2012; Lou, Polk, Skouras
2019). Правило и порог — ВЫВОДЫ.md (записаны до расчёта доходов). Разрыв g = цена перпа в 9:30 ET (закрытие свечи 9:15–9:30)
к цене в 16:00 ET прошлого торгового дня. g ≥ +2% → шорт, g ≤ −2% → лонг (зеркало, отдельный итог); вход в 9:45 ET
(закрытие свечи 9:30–9:45), выход в 16:00 ET, стоп 5%. Общее — tradfi.py.
Запуск из /home/user/mc_data: python3 -I <repo>/research/s264/run.py [count|main]"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tradfi as T  # noqa: E402

TH = 0.02


def events():
    U = T.universe()
    days = T.trading_days()
    rows = []
    for s, grp in U.items():
        S = T.Sym(s)
        for p, d in zip(days[:-1], days[1:]):
            g = S.px(T.ts(d, 9, 30)) / S.px(T.ts(p, 16, 0)) - 1
            if not (abs(g) >= TH):
                continue
            Te, Tx = T.ts(d, 9, 45), T.ts(d, 16, 0)
            k = S.idx(Te)
            if not S.ok(k):
                continue
            rows.append(dict(s=s, grp=grp, d=d, i=k, n=(Tx - Te) // T.BAR, te=Te, side=-1 if g > 0 else 1, mag=abs(g), g=g))
    return pd.DataFrame(rows)


def count():
    E = events()
    for side, nm in ((-1, "разрыв вверх → шорт"), (1, "разрыв вниз → лонг")):
        x = E[E.side == side]
        mo = T.months(x)
        mid = float(np.median(x.te))
        print(f"{nm}: {len(x)} событий ({len(x) / mo:.1f} в месяц), бумаг {x.s.nunique()}, дней {x.d.nunique()}; середина "
              f"{pd.Timestamp(mid, unit='s').date()}; 2-я половина {(x.te >= mid).sum() / ((x.te.max() - mid) / T.MONTH):.1f} в месяц; "
              f"по группам {x.grp.value_counts().to_dict()}")
        print("   по месяцам:", x.groupby(pd.to_datetime(x.te, unit="s").dt.strftime("%Y-%m")).size().to_dict())


def main():
    E = events()
    X = T.trades(E)
    X.to_pickle("s264_trades.pkl")
    T.report(X[X.side == -1], "Г3: разрыв к открытию ≥ +2% → шорт 9:45–16:00 ET")
    T.report(X[X.side == 1], "зеркало: разрыв ≤ −2% → лонг 9:45–16:00 ET")


if __name__ == "__main__":
    {"count": count, "main": main}[sys.argv[1] if len(sys.argv) > 1 else "count"]()
