"""Журнал с фильтром волатильности: из топ-10 по займу выкидываем 4 самых спокойных (волатильность за 7 дней) — 6 шортов в день.
Одна открытая сделка на монету, 7 дней, маржа 1 USDT × 1, комиссия и фандинг; рядом — хедж BTC."""
import datetime
import numpy as np, pandas as pd
exec(open("s10/factor8b.py").read().split("base = ladder()")[0])
d = D[(D.v >= 10e6) & D.ret7.notna()].copy(); d["y7"] = d.ret7 - d.fr7
btc = D[D.s == "BTC"].set_index("T").eval("ret7 - fr7")
pool = d[(d.sh7 > 0) & ~(d.f0 < -0.001)]
top = pool.assign(rr=pool.groupby("T").sh7.rank(ascending=False, method="first")).query("rr <= 10")
for keep, nm in ((10, "топ-10 (без фильтра)"), (6, "топ-10 без 4 самых спокойных"), (5, "топ-10 без 5 самых спокойных")):
    tp = top.assign(vr=top.groupby("T").vol.rank(ascending=False, method="first")).query("vr <= @keep").sort_values("T")
    open_until = {}; tr = []
    for T, g in tp.groupby("T"):
        for s, y in zip(g.s, g.y7):
            if open_until.get(s, 0) > T: continue
            open_until[s] = T + 7 * 86400
            tr.append(dict(T=T, s=s, p=-y - 0.001, h=-y - 0.001 + btc.get(T, np.nan) - 0.001))
    tr = pd.DataFrame(tr); tr["half"] = np.where(tr["T"] < CUT, 1, 2)
    wk = pd.to_datetime(tr["T"], unit="s").dt.to_period("W"); W = tr.groupby(wk)[["p", "h"]].sum(); eq = W.p.cumsum(); eqh = W.h.cumsum()
    days = (tr["T"].max() - tr["T"].min()) / 86400
    print(f"\n{nm}: сделок {len(tr)} ({len(tr)/days*7:.1f} в неделю, открыто ~{len(tr)*7/days:.0f})")
    print(f"   на сделку: шорт {tr.p.mean()*100:+.2f}% (медиана {tr.p.median()*100:+.2f}%, в плюсе {(tr.p > 0).mean():.0%}; 1-я/2-я {tr[tr.half == 1].p.mean()*100:+.2f}/{tr[tr.half == 2].p.mean()*100:+.2f})"
          f" | хедж BTC {tr.h.mean()*100:+.2f}% (в плюсе {(tr.h > 0).mean():.0%}; 1-я/2-я {tr[tr.half == 1].h.mean()*100:+.2f}/{tr[tr.half == 2].h.mean()*100:+.2f})")
    print(f"   маржа 1 USDT ×1: шорт {tr.p.sum():+.1f} USDT (просадка {(eq - eq.cummax()).min():.1f}, недель в плюсе {(W.p > 0).mean():.0%}),"
          f" хедж BTC {tr.h.sum():+.1f} USDT (просадка {(eqh - eqh.cummax()).min():.1f}, недель в плюсе {(W.h > 0).mean():.0%}); хуже −50%: {(tr.p < -0.5).sum()}")
