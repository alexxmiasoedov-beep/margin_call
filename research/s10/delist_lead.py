"""Опережают ли займы (MarginData) объявления Binance о делистинге со спота и о мониторинговом теге? Для каждой монеты:
доля постов канала с монетой и средний BOR за 1, 3, 7 дней до объявления против её же уровня за 30–60 дней до него; реакция цены."""
import pickle, re, datetime
import numpy as np, pandas as pd
A = pickle.load(open("s10/ann.pkl", "rb"))
m = pickle.load(open("s7/margin.pkl", "rb")); G, PT = m["G"], m["PT"]
K = pickle.load(open("s2/k2y.pkl", "rb"))
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
fut = {}
for s in K: fut.setdefault(strip(s), s)
ev = []
for a in A.values():
    if not a["ts"] or a["ts"] < 1741000000000: continue          # MarginData с 20.02.2025 + 2 недели истории
    t = a["title"]
    if re.match(r"Binance Will Delist ", t): typ = "spot_delist"
    elif "Monitoring Tag" in t and "Include" in t: typ = "monitor"
    elif re.match(r"Binance Margin( And Loan)? Will Delist", t): typ = "margin_delist"
    else: continue
    part = t.split(" on ")[0] if typ != "monitor" else re.split(r"Include ", t)[1].split(" on ")[0].split(", Remove")[0]
    part = re.sub(r"^Binance (Margin( And Loan)? )?Will Delist ", "", part)
    for tok in re.split(r",\s*|\s*&\s*|\s+and\s+", part):
        tok = tok.strip()
        if re.match(r"^[A-Z0-9]{2,12}$", tok): ev.append(dict(tok=tok, typ=typ, T=a["ts"] / 1000, title=t))
E = pd.DataFrame(ev).drop_duplicates(["tok", "typ"])
print("событий:", len(E), E.typ.value_counts().to_dict())
PTa = np.array(PT)
rows = []
for x in E.itertuples():
    arr = G.get(x.tok); r = dict(tok=x.tok, typ=x.typ, T=x.T)
    def share(a, b):
        n = ((PTa >= a) & (PTa < b)).sum()
        k = 0 if arr is None else ((arr[:, 0] >= a) & (arr[:, 0] < b)).sum()
        return k / n if n else np.nan
    def bor(a, b):
        if arr is None: return 0.0
        mm = (arr[:, 0] >= a) & (arr[:, 0] < b)
        return float(np.nanmean(arr[mm, 1])) if mm.any() else 0.0
    for nm, d in (("1d", 1), ("3d", 3), ("7d", 7)):
        r[f"sh_{nm}"] = share(x.T - d * 86400, x.T); r[f"bor_{nm}"] = bor(x.T - d * 86400, x.T)
    r["sh_base"] = share(x.T - 60 * 86400, x.T - 30 * 86400); r["bor_base"] = bor(x.T - 60 * 86400, x.T - 30 * 86400)
    s = fut.get(x.tok)
    if s is not None:
        a = K[s]; t = a["t"]; j = int(np.searchsorted(t, x.T)) 
        if 0 < j < len(t) - 96:
            e = float(a["o"][j]); r["ret_1h"] = float(a["c"][j + 3]) / e - 1; r["ret_24h"] = float(a["c"][j + 95]) / e - 1
            r["pre_7d"] = e / float(a["c"][max(0, j - 672)]) - 1
    rows.append(r)
R = pd.DataFrame(rows)
for typ, g in R.groupby("typ"):
    print(f"\n{typ}: монет {len(g)} | в канале за 30–60 дн до объявления (доля постов): {g.sh_base.mean():.2%} | за 7 дн: {g.sh_7d.mean():.2%} | за 3 дн: {g.sh_3d.mean():.2%} | за 1 дн: {g.sh_1d.mean():.2%}")
    gg = g[g.sh_base.notna()]
    print(f"   монет, у которых доля за 3 дня выше базы в 2+ раза и ≥ 10%: {((gg.sh_3d >= 2 * gg.sh_base) & (gg.sh_3d >= 0.1)).sum()} из {len(gg)}")
    if g.ret_24h.notna().any():
        print(f"   цена: за 1 ч после {g.ret_1h.mean()*100:+.1f}%, за 24 ч {g.ret_24h.mean()*100:+.1f}% (n={g.ret_24h.notna().sum()}), за 7 дней до {g.pre_7d.mean()*100:+.1f}%")
R.to_pickle("s10/delist_lead.pkl")
print(R[R.sh_3d > 0].sort_values("sh_3d", ascending=False).head(15)[["tok", "typ", "sh_base", "sh_7d", "sh_3d", "sh_1d", "bor_base", "bor_3d", "ret_24h"]].round(3).to_string())
