"""«Часы фандинга» без заглядывания вперёд.
A — лонг на выплату: сигнал — ставка ПРЕДЫДУЩЕЙ выплаты ≤ порога (известна заранее); вход за 60/30/15 мин до выплаты, выход через 15 мин
    после; лонг получает |ставку| текущей выплаты.
B — шорт после выплаты: сигнал — только что выплаченная ставка ≤ порога; вход через 15 мин после выплаты, выход за 15 мин до
    следующей выплаты, но не позже чем через 4 ч (фандинг не платим). Комиссия 0,1% на сделку."""
import pickle, datetime
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
UTC = datetime.timezone.utc
T0 = datetime.datetime(2024, 10, 19, tzinfo=UTC).timestamp(); T1 = datetime.datetime(2026, 10, 18, tzinfo=UTC).timestamp()
A, Bt = [], []
for s, fr in F.items():
    a = K.get(s)
    if a is None or len(fr) < 3: continue
    t = a["t"]; c = a["c"].astype(np.float64); h = a["h"].astype(np.float64); n = len(t); idx = {int(x): i for i, x in enumerate(t)}
    ci = lambda T: idx.get(int(T) // 900 * 900 - 900)              # свеча, закрывшаяся в момент T
    for k in range(1, len(fr) - 1):
        tk, iv, rk = fr[k]; rp = fr[k - 1][2]; tn = fr[k + 1][0]
        if not (T0 <= tk <= T1): continue
        j0 = ci(tk)
        if j0 is None or j0 < 8 or j0 + 20 >= n: continue
        if rp <= -0.002:
            for lead, lab in ((4, "60"), (2, "30"), (1, "15")):
                if tk - lead * 900 < fr[k - 1][0]: continue           # вход не раньше предыдущей выплаты
                A.append((s, tk, iv, rp, rk, lab, c[j0 + 1] / c[j0 - lead] - 1 - rk - 0.001, c[j0 + 1] / c[j0 - lead] - 1))
        if rk <= -0.002:
            jx = ci(min(tk + 4 * 3600, tn - 900)); je = j0 + 1
            if jx is not None and jx > je:
                Bt.append((s, tk, iv, rk, 1 - c[jx] / c[je] - 0.001, (jx - je) * 0.25, h[je + 1:jx + 1].max() / c[je] - 1))
A = pd.DataFrame(A, columns=["s", "t", "iv", "r_prev", "r_now", "lead", "pnl", "price"])
B = pd.DataFrame(Bt, columns=["s", "t", "iv", "r", "pnl", "hold_h", "maxup"])
for D in (A, B):
    D["year"] = pd.to_datetime(D.t, unit="s").dt.year; D["q"] = pd.to_datetime(D.t, unit="s").dt.to_period("Q").astype(str)
A.to_pickle("s2/fsA.pkl"); B.to_pickle("s2/fsB.pkl")
pd.set_option("display.width", 250)
bins = [-1, -0.015, -0.0075, -0.004, -0.002]
print("=== A: лонг на выплату по ставке прошлой выплаты (в %; цена, итог с выплатой и комиссией)")
A["bin"] = pd.cut(A.r_prev, bins)
print((A.groupby(["lead", "bin"], observed=True).agg(N=("pnl", "size"), монет=("s", "nunique"), ставка_сейчас=("r_now", "mean"), цена=("price", "mean"), итог=("pnl", "mean"))
       * [1, 1, 100, 100, 100]).round(3).to_string())
print("\n=== B: шорт после выплаты до следующей (≤ 4 ч)")
B["bin"] = pd.cut(B.r, bins); B["ivg"] = np.where(B.iv <= 1, "1 ч", "4–8 ч")
print((B.groupby(["ivg", "bin"], observed=True).agg(N=("pnl", "size"), монет=("s", "nunique"), часов=("hold_h", "mean"), итог=("pnl", "mean"), в_плюсе=("pnl", lambda x: (x > 0).mean()))
       * [1, 1, 1, 100, 100]).round(3).to_string())
print("\nB по кварталам, ставка ≤ −0,75%:")
print((B[B.r <= -0.0075].groupby(["ivg", "q"]).pnl.agg(["size", "mean"]) * [1, 100]).round(2).unstack(0).to_string())
