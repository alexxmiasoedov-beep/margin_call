"""s171 — проверка сочетаний «займ ускорился» + показатель (гипотезы и порог — ВЫВОДЫ.md, записаны до расчёта): по половинам
группа с условием против группы без условия; основной исход — шорт 7 сут со стопом +50% (n7), для отчёта — 48 ч со стопом
+25% (n2) и с хеджем BTC. Разница — с t по кластерам дней. Запуск из /home/user/mc_data: python3 <repo>/research/s171/analyze.py"""
import numpy as np
import pandas as pd

CUT = pd.Timestamp("2025-12-01", tz="UTC").timestamp()
DAY = 86400


def dt(a, b, col):
    a, b = a.dropna(subset=[col]), b.dropna(subset=[col])
    if len(a) < 5 or len(b) < 5:
        return np.nan, np.nan
    da = a.groupby(a["T"] // DAY)[col].mean(); db = b.groupby(b["T"] // DAY)[col].mean()
    d = a[col].mean() - b[col].mean(); se = np.sqrt(da.var() / len(da) + db.var() / len(db))
    return d, d / se if se > 0 else np.nan


def ct(x, T):
    x = np.asarray(x, float); g = (np.asarray(T, float) // DAY).astype(np.int64); m = ~np.isnan(x); x, g = x[m], g[m]
    if len(x) < 5:
        return np.nan, np.nan
    u = pd.Series(x - x.mean()).groupby(g).sum().values; G = len(u)
    se = np.sqrt((u ** 2).sum() * G / (G - 1)) / len(x)
    return x.mean(), x.mean() / se


def main():
    E = pd.read_pickle("s171_events.pkl")
    K = {"К1 поток спота: покупки ≤ 45%": (E.buy4 <= 0.45, E.buy4.notna()),
         "К2 OI за 4 ч ≥ +5% при фандинге ≥ 0": ((E.doi4 >= 0.05) & (E.f24 >= 0), E.doi4.notna() & E.f24.notna()),
         "К3 займ за 24 ч ≥ 0,5% капитализации": (E.bmc >= 0.005, E.bmc.notna()) if "bmc" in E else (E.s.isna(), E.s.isna()),
         "К4 разлок ≥ 1% в 14 сут": (E.unl14, E.unl14.notna()),
         "К5 ликвидации шортов ≥ 100 тыс. $ за 4 ч": (E.sqz4 >= 1e5, E.sqz4.notna()),
         "К6 завод на Binance за 24 ч (токены Ethereum)": (E.dep24, E.erc)}
    m, t = ct(E.n7, E["T"])
    print(f"основа З↑: {len(E)} событий, шорт 7 сут {m:+.2%} (t {t:+.1f}); половины "
          f"{E[E['T'] < CUT].n7.mean():+.2%} / {E[E['T'] >= CUT].n7.mean():+.2%}; 48 ч {E.n2.mean():+.2%}")
    for name, (cond, ok) in K.items():
        print(f"\n{name}:")
        for hn, hm in (("1-я половина", E["T"] < CUT), ("2-я половина", E["T"] >= CUT)):
            X = E[hm & ok]; a, b = X[cond[hm & ok]], X[~cond[hm & ok]]
            d7, t7 = dt(a, b, "n7"); d2, t2 = dt(a, b, "n2"); ma, ta = ct(a.n7, a["T"])
            print(f"  {hn}: с условием n={len(a):4d} 7 сут {ma:+.2%} (t {ta:+.1f}) | без n={len(b):4d} {b.n7.mean():+.2%} | "
                  f"разница {d7:+.2%} (t {t7:+.1f}) | 48 ч: {a.n2.mean():+.2%} против {b.n2.mean():+.2%} (t {t2:+.1f}) | "
                  f"с хеджем {a.n7h.mean():+.2%} против {b.n7h.mean():+.2%}")


if __name__ == "__main__":
    main()
