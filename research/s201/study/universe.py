"""s201: вселенная перпов Binance из s2/k2y.pkl — ключи, время торгов, дневные свечи (UTC) за окно Santiment.
Только описание: дневной ход цены и оборот, без доходов после событий. Итог — /home/user/mc_data/s201/perp_daily.pkl."""
import pickle, time
import numpy as np
import pandas as pd

D = "/home/user/mc_data"
t0 = time.time()
K = pickle.load(open(f"{D}/s2/k2y.pkl", "rb"))
print("символов в k2y:", len(K), "загрузка", round(time.time() - t0), "с")
s0 = next(iter(K))
print("пример", s0, type(K[s0]), list(K[s0].keys()) if hasattr(K[s0], "keys") else K[s0].dtype)

W0 = pd.Timestamp("2025-11-01", tz="UTC").timestamp()       # чуть шире окна Santiment (2025-11-19 … 2026-10-20)
rows, live = [], {}
for s, a in K.items():
    t = np.asarray(a["t"], float); qv = np.asarray(a["qv"], float)
    nz = np.flatnonzero(qv > 0)
    live[s] = (float(t[nz[0]]), float(t[nz[-1]])) if len(nz) else (np.nan, np.nan)
    m = t >= W0
    if not m.any():
        continue
    df = pd.DataFrame({"t": t[m], "o": np.asarray(a["o"], float)[m], "h": np.asarray(a["h"], float)[m],
                       "l": np.asarray(a["l"], float)[m], "c": np.asarray(a["c"], float)[m], "qv": qv[m]})
    df = df[df.qv > 0]
    if df.empty:
        continue
    df["d"] = pd.to_datetime(df.t, unit="s", utc=True).dt.floor("D")
    g = df.groupby("d").agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"), qv=("qv", "sum"), n=("t", "size"))
    g["s"] = s
    rows.append(g.reset_index())
P = pd.concat(rows, ignore_index=True)
L = pd.DataFrame([(s, a, b) for s, (a, b) in live.items()], columns=["s", "live0", "live1"])
pickle.dump({"daily": P, "live": L}, open(f"{D}/s201/perp_daily.pkl", "wb"))
print("дневных строк", len(P), "символов с торгами с 2025-11-01:", P.s.nunique())
last = pd.Timestamp("2025-11-19", tz="UTC").timestamp()
alive = L[(L.live1 >= last)]
print("живых в окне (последняя свеча ≥ 2025-11-19):", len(alive))
print("последняя свеча архива:", pd.to_datetime(L.live1.max(), unit="s", utc=True))
print("готово за", round(time.time() - t0), "с")
