"""s96 — портфель журналов по сделкам бэктеста: доход по дням входа, связь журналов между собой, худшие дни, сколько шортов
открыто одновременно. Журналы и их сделки: s20/trades.pkl (📘 канал, 🇰🇷, 🏦, 🇰🇷🆕, 📢, 🆕), s65 (🔝), s83 (👀),
s49 (🛒, доля ≥ 25,9%), s88 (⏰), s23/rule_trades.pkl (🌊, стоп 15%). Сделка — равный вес (маржа 1, доход = доля цены).
Запуск из папки с данными: python3 <путь>/s96/portfolio.py"""
import numpy as np
import pandas as pd

DAY = 86400
HOLD = {"📘": 48, "🇰🇷": 48, "🏦": 168, "🇰🇷🆕": 168, "📢": 168, "🆕": 168, "🔝": 48, "👀": 48, "🛒": 48, "⏰": 48, "🌊": 2}


def load():
    rows = []
    a = pd.read_pickle("s20/trades.pkl")
    for j, x in a.groupby("journal"):
        rows.append(pd.DataFrame({"j": "📘" if j == "канал" else j, "s": x.s, "t": x.te, "r": x.net}))
    a = pd.read_pickle("s65/trades.pkl"); rows.append(pd.DataFrame({"j": "🔝", "s": a.s, "t": a.t, "r": a.S_10_25}))
    a = pd.read_pickle("s83/trades.pkl"); rows.append(pd.DataFrame({"j": "👀", "s": a.s, "t": a.t, "r": a.S_10_25}))
    a = pd.read_pickle("s49/trades.pkl"); a = a[a.share >= 0.259]
    rows.append(pd.DataFrame({"j": "🛒", "s": a.s, "t": a.t, "r": a.net}))
    a = pd.read_pickle("s88/trades.pkl"); a = a[a.open9 & (a.r1 >= 0.05) & (a.share >= 0.20)]
    rows.append(pd.DataFrame({"j": "⏰", "s": a.s, "t": a.t, "r": a.S_10_25}))
    a = pd.read_pickle("s23/rule_trades.pkl")
    rows.append(pd.DataFrame({"j": "🌊", "s": a.s, "t": a["T"], "r": a["net0.15"]}))
    X = pd.concat(rows, ignore_index=True).dropna(subset=["r"])
    X["t"] = X.t.astype(float)
    return X[(X.t >= 1727740800) & (X.t < 1792540800)]


def main():
    X = load()
    X["d"] = (X.t // DAY).astype(int)
    print("Сделок по журналам:", X.j.value_counts().to_dict())
    D = X.pivot_table(index="d", columns="j", values="r", aggfunc="sum").fillna(0.0)
    D = D.reindex(range(D.index.min(), D.index.max() + 1), fill_value=0.0)
    C = D.corr()
    cols = [c for c in ["🇰🇷", "🛒", "🔝", "👀", "⏰", "🇰🇷🆕", "📘", "🏦", "📢", "🌊"] if c in C]
    print("\nКорреляция дохода по дням входа:")
    print(C.loc[cols, cols].round(2).to_string())
    tot = D.sum(axis=1)
    print(f"\nПортфель (все сделки, маржа 1 на сделку): средний день {tot.mean():+.3f}, σ {tot.std():.3f};"
          f" худшие дни: " + ", ".join(f"{pd.Timestamp(d * DAY, unit='s'):%d.%m.%y} {v:+.2f}" for d, v in tot.nsmallest(5).items()))
    worst = tot.nsmallest(10).index
    print("В 10 худших днях — доля по журналам:", (D.loc[worst].sum() / D.loc[worst].sum().sum()).round(2)[cols].to_dict())
    # одновременно открытые шорты (по сроку журнала)
    ev = []
    for j, s, t in zip(X.j, X.s, X.t):
        ev += [(t, 1, s), (t + HOLD.get(j, 48) * 3600, -1, s)]
    ev.sort()
    cur, peak, hist = 0, 0, []
    for t, k, _ in ev:
        cur += k; peak = max(peak, cur); hist.append(cur)
    print(f"Одновременно открытых сделок: в среднем {np.mean(hist):.0f}, максимум {peak}")
    same = X.groupby(["s", "d"]).j.nunique()
    print(f"Монета-день, где вошли 2+ журнала: {(same >= 2).mean():.1%} пар (монета, день); 3+: {(same >= 3).mean():.1%}")


if __name__ == "__main__":
    main()
