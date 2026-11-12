"""Что предшествует сильному росту и падению. Срезы раз в 4 ч, первая половина (поиск). Цель: доход к рынку за 24 ч
вперёд ≥ +25% («рост») или ≤ −20% («обвал»), средний доход к рынку за 1 и 3 суток. Признаки на срезе (ранг среди монет
среза): доход за 24 ч и 72 ч, поток Φ, «цена без потока» D, доля чистых покупок B, оборот к норме A, размер сделки TS,
сжатие волатильности VOL/VOLb, премия и её изменение, фандинг, ветвление η, расстояние до максимума 30 суток, число
прошлых ростов монеты за 90 суток, возраст фьючерса, ликвидность. Для каждого признака — частота роста/обвала и доход
по децилям (подъём к базе). Кэш длинной таблицы — s23/long4h.pkl. Запуск из папки с данными."""
import os
import pickle
import sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from feat23 import CUT, LIQ, build, fwd_ex

PATH = "s23/long4h.pkl"


def long_table():
    if os.path.exists(PATH):
        return pd.read_pickle(PATH)
    F = build(24)
    C, e = F["C"], F["e"]
    idx, cols = C.index.values, C.columns
    X = {k: F[k] for k in ("R", "PHI", "D", "B", "A", "TS", "dPM", "PMW", "F8", "Vb", "lam")}
    X["R72"] = e.rolling(72, min_periods=72).sum()
    X["R7d"] = e.rolling(168, min_periods=168).sum()
    X["VC"] = F["VOL"] / F["VOLb"]
    X["DH30"] = np.log(C / C.rolling(720, min_periods=240).max())
    X["DL30"] = np.log(C / C.rolling(720, min_periods=240).min())
    big = (np.exp(F["R"]) - 1 >= 0.25).astype(float).where(F["R"].notna())       # был рост ≥ 25% за 24 ч (к рынку)
    day = idx // 86400
    day_big = big.groupby(day).max()
    cnt = day_big.rolling(90, min_periods=1).sum().shift(1)                       # дней с ростом за 90 суток до
    X["NPUMP"] = pd.DataFrame(cnt.reindex(day).values, index=C.index, columns=cols)
    alive = C.notna().values
    first = np.where(alive.any(axis=0), idx[np.argmax(alive, axis=0)], np.nan)
    X["AGE"] = pd.DataFrame((idx[:, None] - first[None, :]) / 86400, index=C.index, columns=cols).where(C.notna())
    E = pickle.load(open("s23/eta.pkl", "rb"))["ETA3"]
    X["ETA3"] = E.reindex(C.index.union(E.index)).ffill(limit=23).reindex(C.index).reindex(columns=cols)
    Y = {f"Y{h}": fwd_ex(C, h) for h in (24, 72)}
    si = np.flatnonzero((idx % (4 * 3600) == 0) & (idx >= idx[0] + 40 * 86400))
    ok = (X["Vb"].values[si] >= LIQ) & np.isfinite(C.values[si])
    ok &= ok.sum(axis=1, keepdims=True) >= 30
    r, c = np.nonzero(ok)
    L = pd.DataFrame({k: v.values[si][r, c] for k, v in {**X, **Y}.items()})
    L["T"] = idx[si][r]; L["s"] = cols.values[c]
    L.to_pickle(PATH)
    return L


if __name__ == "__main__":
    L = long_table()
    L = L[L["T"] < CUT]
    L = L[L.Y24.notna()]
    L["PUMP"] = (L.Y24 >= 0.25).astype(float); L["DUMP"] = (L.Y24 <= -0.20).astype(float)
    print(f"первая половина: срезов {L['T'].nunique()}, строк {len(L)}, ростов ≥ 25% за 24 ч {L.PUMP.mean() * 100:.2f}% строк, "
          f"обвалов ≤ −20% {L.DUMP.mean() * 100:.2f}%")
    feats = ["R", "R72", "R7d", "PHI", "D", "B", "A", "TS", "VC", "PMW", "dPM", "F8", "ETA3", "DH30", "DL30", "NPUMP", "AGE", "Vb", "lam"]
    for f in feats:
        x = L.groupby("T")[f].rank(pct=True)
        g = np.floor((x * 10).clip(0, 9.999)).astype("Int64") if f not in ("NPUMP",) else None
        if f == "NPUMP":
            g = L[f].clip(0, 5).astype("Int64")
        t = L.assign(g=g).dropna(subset=["g"]).groupby("g").agg(n=("PUMP", "size"), pump=("PUMP", "mean"), dump=("DUMP", "mean"),
                                                                   y24=("Y24", "mean"), y72=("Y72", "mean"))
        base_p, base_d = L.PUMP.mean(), L.DUMP.mean()
        print(f"\n{f}: подъём к базе (рост / обвал) и средний доход к рынку 1 и 3 сут по децилям (0 — меньше)")
        print("   " + " | ".join(f"{int(k)}: {r.pump / base_p:4.2f}/{r.dump / base_d:4.2f} {r.y24 * 100:+.2f}/{r.y72 * 100:+.2f}"
                                  for k, r in t.iterrows()))
