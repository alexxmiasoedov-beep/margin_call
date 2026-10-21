"""CoinGecko на момент пампа (только последние 365 дней — ограничение бесплатного API): капитализация, оборот фьючерса к
капитализации, открытый интерес к капитализации, FDV к капитализации (текущий снимок). Проверка на корейском шорте, лонге 🟩 и всех пампах."""
import json, os, re, datetime
import numpy as np, pandas as pd
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
M = {x["id"]: x for x in json.load(open("s7/cg/markets.json"))}; MAP = json.load(open("s7/cg/map.json"))
H = {}
for sy, cid in MAP.items():
    fn = f"s7/cg/{sy}.json"
    if not os.path.exists(fn): continue
    j = json.load(open(fn)); mc = np.array(j.get("market_caps") or [], dtype=float); tv = np.array(j.get("total_volumes") or [], dtype=float)
    if len(mc) > 30: H[sy] = (mc[:, 0] / 1000, mc[:, 1], tv[:, 1] if len(tv) == len(mc) else np.full(len(mc), np.nan), M.get(cid, {}))
D = pd.read_pickle("s7/feat_pump2.pkl")
rows = []
for s, t, v24, oi in zip(D.s, D.t, D.v24, D.m_oi_usd):
    h = H.get(strip(s).lower()); r = {}
    if h is not None:
        k = np.searchsorted(h[0], t, "right") - 1
        if k >= 0 and t - h[0][k] < 2 * 86400 and h[1][k] > 0:
            mc = h[1][k]; snap = h[3]
            r = dict(cg_mcap=np.log10(mc), cg_turn=v24 / mc, cg_oi_mc=oi / mc if oi == oi else np.nan, cg_vol_mc=h[2][k] / mc,
                     cg_fdv_mc=(snap.get("fully_diluted_valuation") or np.nan) / max(snap.get("market_cap") or np.nan, 1))
    rows.append(r)
C = pd.DataFrame(rows, index=D.index); D = pd.concat([D, C], axis=1); D.to_pickle("s7/feat_pump3.pkl")
print("пампов с данными CoinGecko:", D.cg_mcap.notna().sum(), "из", len(D), "| с", pd.to_datetime(D[D.cg_mcap.notna()].t.min(), unit="s"))
E = D[D.cg_mcap.notna()]
def show(nm, g, col):
    print(f"\n{nm} ({col}), по третям признака (только 2-й год, где есть данные):")
    for f in ("cg_mcap", "cg_turn", "cg_oi_mc", "cg_vol_mc", "cg_fdv_mc"):
        x = g[f]
        if x.notna().sum() < 90: continue
        q = pd.qcut(x.rank(method="first"), 3, labels=False)
        print(f"  {f:10s} " + " | ".join(f"треть {b + 1} (≤ {g[q == b][f].max():.3g}): {(q == b).sum()} WR {(g[q == b][col] > 0).mean():.0%} {g[q == b][col].mean() * 100:+.2f}%" for b in range(3)))
show("корейский шорт", E[E.kshare >= 0.2], "S_10_25")
show("лонг 🟩", E[(E.sshare < 0.12) & (E.snorm >= 0.03) & (E.kshare < 0.2) & (E.fshare < 0.1)], "L_30_15")
show("все пампы, шорт", E, "S_10_25")
show("все пампы, лонг", E, "L_30_15")
