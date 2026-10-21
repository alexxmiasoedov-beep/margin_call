"""Место в списке «лидеры роста за 24 ч»: зависит от чужих монет, то есть для самой монеты случайно.
Сравниваем монеты с одинаковым ростом за 24 ч, но разным местом в списке."""
import pickle, datetime
import numpy as np, pandas as pd
T = np.load("s4/T.npy"); C = np.load("s4/G_c.npy"); Q = np.load("s4/G_qv.npy"); syms = pickle.load(open("s4/syms.pkl", "rb"))
n, m = C.shape; first = np.argmax(~np.isnan(C), axis=0)
UTC = datetime.timezone.utc; A = datetime.datetime(2024, 10, 19, tzinfo=UTC).timestamp(); CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp()
rows = []
for i in range(np.searchsorted(T, A), n - 97, 4):
    c = C[i]; p = C[i - 96]; ok = ~np.isnan(c) & ~np.isnan(p) & (first + 672 <= i)
    ch = np.where(ok, c / p - 1, np.nan); valid = np.flatnonzero(ok)
    if len(valid) < 100: continue
    order = valid[np.argsort(-ch[valid])]; rk = np.empty(m, int); rk[order] = np.arange(1, len(order) + 1)
    sel = valid[ch[valid] >= 0.10]
    if not len(sel): continue
    v24 = np.nansum(Q[i - 95:i + 1, sel], axis=0)
    f1 = C[i + 4, sel] / c[sel] - 1; f4 = C[i + 16, sel] / c[sel] - 1; f24 = C[i + 96, sel] / c[sel] - 1
    top1 = ch[order[0]]; top10 = ch[order[min(9, len(order) - 1)]]
    for k, s in enumerate(sel):
        rows.append((T[i], s, ch[s], rk[s], v24[k], f1[k], f4[k], f24[k], len(valid), top1, top10))
D = pd.DataFrame(rows, columns=["t", "s", "ch", "rk", "v24", "f1", "f4", "f24", "nv", "top1", "top10"])
D["y"] = np.where(D.t < CUT, 1, 2); D.to_pickle("s4/rank.pkl"); print(len(D))
D = D[D.v24 >= 5e6]
D["chb"] = pd.cut(D.ch, [0.1, 0.15, 0.2, 0.3, 0.5, 1.0, 100]); D["rkb"] = pd.cut(D.rk, [0, 1, 3, 10, 30, 10**6], labels=["1", "2-3", "4-10", "11-30", "31+"])
for f in ("f1", "f4", "f24"):
    print(f"\nвперёд {f}, средняя доходность лонга, % (число наблюдений)")
    pv = D.pivot_table(index="chb", columns="rkb", values=f, aggfunc="mean", observed=True) * 100
    cnt = D.pivot_table(index="chb", columns="rkb", values=f, aggfunc="count", observed=True)
    print(pv.round(2).astype(str).add(" (").add(cnt.fillna(0).astype(int).astype(str)).add(")").to_string())
