"""s201: общая панель «день × перп» из дневных рядов Santiment (основной slug перпа; для ончейн-метрик, которых нет
у основного slug, — вариант сети bnb-/arb-/o-/a-/p-). Плюс дневные свечи перпа (только описание дня: ход открытие →
закрытие, максимум, оборот) и предложение в обращении по Santiment (marketcap_usd / price_usd).
Итог — /home/user/mc_data/s201/panel.pkl: dict метрика → DataFrame (индекс — день UTC, столбцы — перп)."""
import glob
import os
import pickle

import numpy as np
import pandas as pd

D = "/home/user/mc_data/s201"
G = pd.read_csv(f"{D}/map.csv")
V = pd.read_csv(f"{D}/map_variants.csv")
DAYS = pd.date_range("2025-11-20", "2026-10-19", tz="UTC")
prim = dict(zip(G.s, G.slug))
var = V.groupby("s").slug.apply(list).to_dict()


def wide(name):
    d = pd.read_pickle(f"{D}/daily/{name}.pkl")
    d["d"] = d.datetime.dt.floor("D")
    w = d.pivot_table(index="d", columns="slug", values="value", aggfunc="last").reindex(DAYS)
    out = {}
    for s, sl in prim.items():
        if sl in w.columns and w[sl].notna().any():
            out[s] = w[sl]
        else:
            for v in var.get(s, []):
                if v in w.columns and w[v].notna().any():
                    out[s] = w[v]
                    break
    return pd.DataFrame(out, index=DAYS)


PAN = {}
for f in sorted(glob.glob(f"{D}/daily/*.pkl")):
    name = os.path.basename(f)[:-4]
    PAN[name] = wide(name)
px = pd.read_pickle(f"{D}/price_usd_daily.pkl")
px = px.pivot_table(index="d", columns="slug", values="value", aggfunc="last").reindex(DAYS)
PAN["price_usd"] = pd.DataFrame({s: px[sl] for s, sl in prim.items() if sl in px.columns}, index=DAYS)
PAN["circ"] = (PAN["marketcap_usd"] / PAN["price_usd"]).replace([np.inf, -np.inf], np.nan)
U = pickle.load(open(f"{D}/perp_daily.pkl", "rb"))["daily"]
U = U[U.s.isin(prim)]
for k in ("o", "h", "l", "c", "qv"):
    PAN["perp_" + k] = U.pivot_table(index="d", columns="s", values=k).reindex(DAYS)
pickle.dump(PAN, open(f"{D}/panel.pkl", "wb"))
print("метрик в панели:", len(PAN))
for k, v in PAN.items():
    print(f"  {k}: перпов {v.shape[1]}, непустых ячеек {int(v.notna().sum().sum())}")
