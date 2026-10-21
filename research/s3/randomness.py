"""Тесты случайности минутного пути цены внутри пампа (от спокойной базы до свечи, где достигнуто +15%) и за 6 ч до базы:
отношение дисперсий VR(5), z-статистика серий знаков, доля растущих минут, самая длинная серия роста, доля хода за одну минуту,
ровность хода. Связь с откатом: шорт в момент пампа (15/15/24 ч из rev_trade) — по половинам месяца, Корея / не Корея."""
import pickle, os, datetime
import numpy as np, pandas as pd, scipy.stats as st
K = pickle.load(open("kaia/k15_all.pkl", "rb")); F = pickle.load(open("mm2/rev_feats_pnl.pkl", "rb"))
MSK = datetime.timezone(datetime.timedelta(hours=3)); MID = datetime.datetime(2026, 10, 4, tzinfo=MSK).timestamp()
EV = {}
for f in F: EV.setdefault(f["ev"], []).append(f)
def rtests(c):
    r = np.diff(np.log(c)); r = r[np.isfinite(r)]
    if len(r) < 20 or r.std() == 0: return {}
    n = len(r); r5 = np.log(c[5::5] / c[:-5:5]) if len(c) > 10 else np.array([])
    vr = r5.var() / (5 * r.var()) if len(r5) > 3 else np.nan
    sg = np.sign(r); sg = sg[sg != 0]; runs = 1 + (sg[1:] != sg[:-1]).sum() if len(sg) > 1 else np.nan
    p = (sg > 0).mean() if len(sg) else np.nan; nn = len(sg)
    mu = 1 + 2 * nn * p * (1 - p); sd = np.sqrt(max(2 * nn * p * (1 - p) * (2 * nn * p * (1 - p) - 1) / max(nn - 1, 1), 1e-9))
    best = cur = 0
    for x in sg:
        cur = cur + 1 if x > 0 else 0; best = max(best, cur)
    tot = np.abs(r).sum()
    return dict(vr5=vr, runs_z=(runs - mu) / sd, up_frac=p, max_run=best, top1=np.abs(r).max() / tot, eff=abs(r.sum()) / tot)
rows = []
for ev, ms in EV.items():
    s, i = ev; m0 = min(ms, key=lambda f: f["i"])
    raw = f"mm2/raw2/{s}.pkl"
    if not os.path.exists(raw): continue
    fut = pickle.load(open(raw, "rb")).get("fut")
    if fut is None: continue
    tb = K[s][i, 0] + 900; tp = K[s][m0["i"], 0] + 900
    w = fut[(fut[:, 0] >= tb) & (fut[:, 0] < tp)]; pre = fut[(fut[:, 0] >= tb - 6 * 3600) & (fut[:, 0] < tb)]
    a = rtests(w[:, 4]) if len(w) > 20 else {}; b = rtests(pre[:, 4]) if len(pre) > 60 else {}
    rows.append(dict(s=s, t=tp, pnl=m0["pnl"], kr=m0.get("kr_share_1h", np.nan), mins=len(w), **{f"p_{k}": v for k, v in a.items()}, **{f"b_{k}": v for k, v in b.items()}))
D = pd.DataFrame(rows); D.to_pickle("s3/randomness.pkl")
print(f"пампов {len(D)}, шорт 15/15/24 в среднем {D.pnl.mean() * 100:+.2f}%")
for k in [c for c in D.columns if c.startswith(("p_", "b_"))] + ["mins"]:
    v = D[k]; ok = v.notna()
    if ok.sum() < 100: continue
    q = pd.qcut(v[ok], 4, duplicates="drop"); line = f"{k:10s} ρ={st.spearmanr(v[ok], D.pnl[ok])[0]:+.2f} |"
    for b, d in D[ok].groupby(q, observed=True):
        h1 = d[d.t < MID].pnl.mean() * 100; h2 = d[d.t >= MID].pnl.mean() * 100; nk = d[~(d.kr >= 0.2)].pnl.mean() * 100
        line += f" ≤{b.right:.3g}: {d.pnl.mean() * 100:+.1f} ({h1:+.1f}/{h2:+.1f}; без корейцев {nk:+.1f})"
    print(line)
