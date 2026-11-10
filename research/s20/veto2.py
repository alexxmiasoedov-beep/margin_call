"""Сквиз-вето — устойчивость (по s20/trades.pkl из veto.py): для каждого журнала и вето — убранные сделки по половинам
истории, разница средних «убранные − оставшиеся» с t-статистикой (Уэлч), изменение итога; плюс заранее заданная
комбинация «китайский профиль без спота»: F или FX или OI или I. Запуск из папки с данными: python3 s20/veto2.py"""
import numpy as np, pandas as pd

T = pd.read_pickle("s20/trades.pkl")
V = {
    "F фандинг ≤ −0,1%/8 ч": lambda x: x.f8 <= -0.001,
    "FX минимум за сутки ≤ −0,75%": lambda x: x.fmin <= -0.0075,
    "OI рост за 24 ч ≥ +50%": lambda x: x.oi24 >= 0.5,
    "I интервал фандинга укорочен": lambda x: x.short_int.astype(bool),
    "S нет спота Binance": lambda x: ~x.spot.astype(bool),
    "B OI ≥ остатка на Binance": lambda x: x.oib >= 1.0,
    "F или FX или OI или I": lambda x: (x.f8 <= -0.001) | (x.fmin <= -0.0075) | (x.oi24 >= 0.5) | x.short_int.astype(bool),
}


def welch(a, b):
    if len(a) < 5 or len(b) < 5:
        return np.nan
    return (a.mean() - b.mean()) / np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))


if __name__ == "__main__":
    for name, j in T.groupby("journal", sort=False):
        cut = j.te.median(); h = j.te < cut
        print(f"\n===== {name}: сделок {len(j)}, итог {j.net.sum():+.2f}, на сделку {j.net.mean() * 100:+.2f}%")
        for vn, f in V.items():
            m = np.asarray(f(j).fillna(False), bool)
            if m.sum() == 0:
                continue
            r, k = j[m], j[~m]
            r1, r2 = r[h[m].values], r[~h[m].values]
            print(f"  {vn:28s} убрано {m.sum():4d} ({m.mean():3.0%}): {r.net.mean() * 100:+6.2f}% (1-я/2-я {r1.net.mean() * 100:+6.2f}/{r2.net.mean() * 100:+6.2f}%, "
                  f"стопов {r.stop.mean():3.0%}) против оставшихся {k.net.mean() * 100:+6.2f}% | t = {welch(r.net, k.net):+5.1f} | "
                  f"итог {j.net.sum():+6.2f} → {k.net.sum():+6.2f}")
