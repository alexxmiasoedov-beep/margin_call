"""Отпечаток ММ по выводам с Binance (s207): число разных токенов (из 261), которые адрес выводил с Binance. Сверка с открытыми метками ММ.
И доля событий 🐋 (s182_origin, src1 = отправитель на адрес пополнения), у которых src1 — «многотокенный» адрес или помечен как ММ."""
import json, collections, pandas as pd, numpy as np
MM = json.load(open("work/mm_labels_eth.json"))
w = pd.read_pickle("/home/user/mc_data/s207_withdrawals.pkl")
print(w.kind.value_counts().to_dict())
ww = w[w.kind == "wallet"]
g = ww.groupby("to").agg(ntok=("tok", "nunique"), n=("tx", "count"), t0=("t", "min"), t1=("t", "max"))
g["mm"] = [MM.get(a, (None,))[0] for a in g.index]
print("адресов-получателей:", len(g))
for k in (1, 2, 3, 5, 10, 20, 40):
    s = g[g.ntok >= k]
    print(f"ntok>={k:>2}: адресов {len(s):>6}, из них с меткой ММ {s.mm.notna().sum():>4} ({s.mm.notna().mean()*100:.1f}%)")
print("метки ММ среди получателей выводов:", g.mm.notna().sum(), collections.Counter(g.mm.dropna()).most_common())
print("ntok у помеченных ММ: медиана", g[g.mm.notna()].ntok.median(), "у прочих", g[g.mm.isna()].ntok.median())
top = g.sort_values("ntok", ascending=False).head(25)
print(top[["ntok", "n", "mm"]].to_string())
# 🐋 events origin
o = pd.read_pickle("/home/user/mc_data/s182_origin.pkl")
o["src1"] = o.src1.str.lower()
o["mm1"] = [MM.get(a, (None,))[0] for a in o.src1]
o["ntok1"] = [g.ntok.get(a, 0) for a in o.src1]
o["y"] = pd.to_datetime(o.t, unit="s").dt.year
print("событий 🐋:", len(o))
print("src1 с меткой ММ:", o.mm1.notna().sum(), collections.Counter(o.mm1.dropna()).most_common())
for k in (3, 5, 10):
    print(f"src1 выводил с Binance >= {k} разных токенов: {(o.ntok1 >= k).sum()} ({(o.ntok1 >= k).mean()*100:.1f}%)")
per = o.groupby("y").agg(n=("tx", "count"), mm=("mm1", lambda s: s.notna().sum()), m5=("ntok1", lambda s: (s >= 5).sum()))
print(per.to_string())
# месяцы 2024-10..2026-10
r = o[(o.t >= 1727740800) & (o.t < 1792800000)]
mon = (r.t.max() - r.t.min()) / 86400 / 30.4
print(f"2024-10..: событий {len(r)} за {mon:.1f} мес; ММ-метка {r.mm1.notna().sum()} ({r.mm1.notna().sum()/mon:.1f}/мес); ntok>=5 {(r.ntok1>=5).sum()} ({(r.ntok1>=5).sum()/mon:.1f}/мес); ntok>=10 {(r.ntok1>=10).sum()} ({(r.ntok1>=10).sum()/mon:.1f}/мес)")
print(o.end.value_counts().head(10).to_dict())
