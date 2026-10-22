"""Как будет работать журнал в боте: каждый день в 01:00 UTC шорт монет из топ-10 фактора займа, которых нет среди открытых;
каждая сделка держится 7 дней (одна открытая сделка на монету). Маржа 1 USDT, плечо ×1, комиссия 0,1% за круг, фандинг.
Рядом — тот же результат с хеджем BTC (лонг BTC на ту же сумму на те же 7 дней)."""
import datetime
import numpy as np, pandas as pd
exec(open("s10/factor8b.py").read().split("base = ladder()")[0])
d = D[(D.v >= 10e6) & D.ret7.notna()].copy(); d["y7"] = d.ret7 - d.fr7
btc = D[D.s == "BTC"].set_index("T").eval("ret7 - fr7")
for N in (10, 5):
    pool = d[(d.sh7 > 0) & ~(d.f0 < -0.001)]
    top = pool.assign(rr=pool.groupby("T").sh7.rank(ascending=False, method="first")).query("rr <= @N").sort_values("T")
    open_until = {}; tr = []
    for T, g in top.groupby("T"):
        for s, y in zip(g.s, g.y7):
            if open_until.get(s, 0) > T: continue
            open_until[s] = T + 7 * 86400
            tr.append(dict(T=T, s=s, p=-y - 0.001, h=-y - 0.001 + btc.get(T, np.nan) - 0.001))
    tr = pd.DataFrame(tr); tr["half"] = np.where(tr["T"] < CUT, 1, 2)
    wk = pd.to_datetime(tr["T"], unit="s").dt.to_period("W")
    W = tr.groupby(wk)[["p", "h"]].sum(); eq = W.p.cumsum(); eqh = W.h.cumsum()
    days = (tr["T"].max() - tr["T"].min()) / 86400
    print(f"\nтоп-{N}: сделок {len(tr)} ({len(tr)/days*7:.1f} в неделю), открыто одновременно в среднем {len(tr)*7/days:.0f}")
    print(f"   на сделку: шорт {tr.p.mean()*100:+.2f}% (медиана {tr.p.median()*100:+.2f}%, в плюсе {(tr.p > 0).mean():.0%}; 1-я/2-я {tr[tr.half == 1].p.mean()*100:+.2f}/{tr[tr.half == 2].p.mean()*100:+.2f})"
          f" | с хеджем BTC {tr.h.mean()*100:+.2f}% (в плюсе {(tr.h > 0).mean():.0%}; 1-я/2-я {tr[tr.half == 1].h.mean()*100:+.2f}/{tr[tr.half == 2].h.mean()*100:+.2f})")
    print(f"   при марже 1 USDT ×1 на сделку: итог шорт {tr.p.sum():+.1f} USDT (просадка {(eq - eq.cummax()).min():.1f}, недель в плюсе {(W.p > 0).mean():.0%}),"
          f" с хеджем BTC {tr.h.sum():+.1f} USDT (просадка {(eqh - eqh.cummax()).min():.1f}, недель в плюсе {(W.h > 0).mean():.0%})")
    print(f"   худшая сделка {tr.p.min()*100:+.0f}% ({tr.loc[tr.p.idxmin(), 's']}), сделок хуже −30%: {(tr.p < -0.3).sum()}, хуже −50%: {(tr.p < -0.5).sum()}")
