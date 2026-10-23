"""Итоговые журналы (обновлено): (A) 🆕 первое появление токена в маржинальном канале при свежем спотовом листинге Binance
(±10 сут) — вход через 24 ч после первого поста, если фандинг ≥ −0,1%/8 ч; 21 сут; стоп +60%; выход при фандинге ≤ −0,5%/8 ч
дважды; (B) 📢 объявления — вход ≤ 15 мин, 7 сут, стоп +25%, без входа при фандинге < −0,1%/8 ч."""
import sys, os, datetime
sys.path.insert(0, os.getcwd())
from s12.lib import *
import pandas as pd
src = open("s12/firstborrow.py").read()
exec(src[src.index("F0 = "):src.index("print(f\"токенов")])
outA = []
for c, s, t1, fresh, age in ev:
    if not fresh: continue
    te = t1 + 24 * 3600; f8 = fnow(s, te)
    if f8 is not None and f8 < -0.001: continue
    r = trade_at(s, K[s], te, 21, 0.6, -0.005)
    if r: outA.append(dict(s=s, te=te, sp=r[0], h=r[1]))
outB = []
for kind_, s, ts in ann_events():
    r = ann_trade(s, ts, 15, 7, 0.25)
    if r is None or (r[3] is not None and r[3] < -0.001): continue
    outB.append(dict(s=s, te=r[0], sp=r[1], h=r[2], kind=kind_))
def journal(nm, o, hold_d):
    o = pd.DataFrame(o).sort_values("te"); busy = {}; keep = []
    for i, r in o.iterrows():
        if busy.get(r.s, 0) > r.te: continue
        busy[r.s] = r.te + hold_d * 86400; keep.append(i)
    j = o.loc[keep]; hh = j.te < CUT
    m = j.groupby(pd.to_datetime(j.te, unit="s").dt.to_period("M")).sp.sum()
    eq = j.sp.cumsum(); dd = (eq - eq.cummax()).min(); span = (j.te.max() - j.te.min()) / 86400 / 30.4
    print(f"{nm}: сделок {len(j)} ({len(j)/span:.1f} в месяц), {j.sp.mean()*100:+.1f}% на сделку (медиана {j.sp.median()*100:+.1f}, в плюсе {(j.sp > 0).mean():.0%}; "
          f"1-я {j[hh].sp.mean()*100:+.1f} / 2-я {j[~hh].sp.mean()*100:+.1f}); с хеджем BTC {j.h.mean()*100:+.1f}%; "
          f"итог при 1 USDT × 1 — {j.sp.sum():+.1f} USDT, просадка {dd:.1f} USDT, месяцев с итогом в плюсе {(m > 0).sum()}/{len(m)}")
    y = j.groupby(pd.to_datetime(j.te, unit="s").dt.year).sp.agg(["mean", "size"])
    print("   по годам:", "; ".join(f"{k}: {r['mean']*100:+.1f}% ({r['size']:.0f})" for k, r in y.iterrows()))
    return j
jA = journal("A 🆕 первый займ свежего токена", outA, 21)
jB = journal("B 📢 объявления Binance", outB, 7)
pd.to_pickle(dict(A=jA, B=jB), "s12/final_journals.pkl")
