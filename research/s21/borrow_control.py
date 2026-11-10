"""Проверки находки borrow_study.py «займ или отдача ускорились при сильном ходе цены → монета отстаёт от рынка»:

1. Контроль «тот же ход цены без займов»: (а) монеты канала с ходом ±5% за 4 ч, но без ускорения займа и отдачи;
   (б) все фьючерсы Binance вне канала в тот же час с ходом ±5% за 4 ч. Если отстают так же — дело в ходе цены, а не в займах.
2. Пересечение ячейки «займ ускорился, цена −5%−» с журналами бота (s20/trades.pkl: канал, 🇰🇷, 🏦, 🇰🇷🆕, 📢, 🆕):
   у скольких входов та же монета была в журнале за сутки до/после; доходность делим только по входам журналов ДО нашего
   (вход журнала после нашего — заглядывание вперёд).
Нужны s21/panel.pkl (borrow_study.py) и s20/trades.pkl (research/s20/veto.py). Запуск из папки с данными."""
import os
import sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15")); sys.path.insert(0, HERE)
from common import BAR, K, live
from borrow_study import HS, H, line, market_grid, thin
from borrow_trades import sims

D = pd.read_pickle("s21/panel.pkl")


def outside(grid, MK):
    """Все фьючерсы вне канала: часы с ходом ±5% за 4 ч, исход шорта к рынку через 24 / 72 / 168 ч."""
    inch = {}
    for s, g in D.groupby("s"):
        inch[s] = set(g["T"].values.tolist())
    rows = []
    for s, a in K.items():
        t = a["t"].astype(np.int64) + BAR; lo, hi = live(s)
        i = np.searchsorted(grid, t); ok = (i < len(grid)) & (grid[np.minimum(i, len(grid) - 1)] == t) & (a["qv"] > 0)
        c = np.full(len(grid), np.nan); c[i[ok]] = a["c"][ok]
        g = np.arange(4, len(grid)); r4 = c[g] / c[g - 4] - 1
        hit = np.isfinite(r4) & (np.abs(r4) >= 0.05) & (grid[g] - BAR >= lo + 86400) & (grid[g] <= hi)
        mine = inch.get(s, set())
        last = {1: -1e18, -1: -1e18}
        for k in g[hit]:
            T = int(grid[k]); sg = 1 if c[k] / c[k - 4] - 1 > 0 else -1
            if T in mine or T - last[sg] < 86400:
                continue
            last[sg] = T
            r = dict(s=s, T=T, r4=c[k] / c[k - 4] - 1)
            for h in HS:
                if k + h < len(grid) and np.isfinite(c[k + h]) and grid[k + h] <= hi + BAR and np.isfinite(MK[h][k]):
                    r[f"x{h}"] = 1 - c[k + h] / c[k] + MK[h][k]
                    r[f"n{h}"] = np.nan
            rows.append(r)
    return pd.DataFrame(rows)


def overlap():
    print("\n2. Пересечение «займ ускорился, цена −5%−» с журналами бота (та же монета за сутки до входа / в следующие сутки):")
    A = pd.read_pickle("s21/cell_A.pkl")
    J = pd.read_pickle("s20/trades.pkl")
    J["sb"] = J.s.str.replace(r"^(1000000|100000|10000|1000)", "", regex=True)
    A["sb"] = A.s.str.replace(r"^(1000000|100000|10000|1000)", "", regex=True)
    before = {}
    for name, g in J.groupby("journal"):
        idx = g.groupby("sb").te.apply(lambda x: np.sort(x.values)).to_dict()
        near = lambda a, b: np.array([bool(np.any(((v := idx.get(sb, np.zeros(0))) - T >= a) & (v - T <= b)))
                                      for sb, T in zip(A.sb, A["T"])])
        before[name] = near(-86400, 0)
        print(f"  {name:6s} до входа {before[name].mean():5.1%}, в следующие сутки {near(1, 86400).mean():5.1%}")
    anyj = np.any(np.vstack(list(before.values())), axis=0)
    print(f"  хоть один журнал до входа: {anyj.mean():.1%}")
    R = sims(A, sl=0.25, hold_h=168)
    R = R.merge(A.assign(anyj=anyj)[["s", "T", "anyj"]], on=["s", "T"])
    for nm, m in (("все", R.net == R.net), ("без журналов до входа", ~R.anyj), ("с журналами до входа", R.anyj)):
        x = R.net[m]
        print(f"  168 ч, стоп 25%, {nm:21s}: n={m.sum()}, {x.mean() * 100:+.2f}% на сделку (t {x.mean() / x.std() * np.sqrt(len(x)):+.1f}), "
              f"с хеджем BTC {R.hedged[m].mean() * 100:+.2f}%")


if __name__ == "__main__":
    if sys.argv[1:] == ["2"]:
        overlap(); sys.exit()
    cut = float(D["T"].median()); base = thin(D)
    up, dn = D.r4 >= 0.05, D.r4 <= -0.05
    acc_b = (D.bor >= 1.5 * D.bor4) & (D.bor >= 50e3) & D.in4
    acc_r = (D.rep >= 1.5 * D.rep4) & (D.rep >= 20e3) & D.in4
    print("1а. Монеты канала (в канале и 4 ч назад), ход цены есть, займ и отдача НЕ ускорялись:")
    for pn, p in (("цена +5%+", up), ("цена −5%−", dn)):
        print(f"  {pn:10s} {line(thin(D[D.in4 & ~acc_b & ~acc_r & p]), base, cut)}")
    print("   для сравнения — займ ускорился:")
    for pn, p in (("цена +5%+", up), ("цена −5%−", dn)):
        print(f"  {pn:10s} {line(thin(D[acc_b & ~acc_r & p]), base, cut)}")

    grid, MK = market_grid()
    O = outside(grid, MK)
    O["n24"] = O["n72"] = O["n168"] = np.nan
    print(f"\n1б. Все фьючерсы вне канала с ходом ±5% за 4 ч (одно наблюдение на монету и направление за сутки), "
          f"t — к той же базе канала:")
    for pn, p in (("цена +5%+", O.r4 >= 0.05), ("цена −5%−", O.r4 <= -0.05)):
        print(f"  {pn:10s} {line(O[p], base, cut)}")

    overlap()
