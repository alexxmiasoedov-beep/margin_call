"""(1) Разрыв «ставка займа против фандинга»: займ на споте дорогой, а шорт на фьючерсе ещё дешёвый → шорт недооценён?
spread = дневная ставка займа + 3 × фандинг за 8 ч (фандинг < 0 — шорт платит). (2) Скачок ставки у монет вне канала → лонг?"""
import datetime, pickle
import numpy as np, pandas as pd
exec(open("s11/rate_factor.py").read().split('print(f"строк с объёмом')[0])
dr = dr[dr.f0.notna()].copy()
dr["fday"] = -dr.f0 * 3                                  # сколько шорт платит в сутки на фьючерсе (доля)
dr["spr"] = dr.rate0 - dr.fday
print("# 1. Разрыв «ставка займа − плата шорта на фьючерсе» (сутки): квинтили, доход ЛОНГА 7 суток с фандингом")
x = dr.copy(); x["q"] = x.groupby("T").spr.transform(lambda v: pd.qcut(v.rank(method="first"), 5, labels=False) if len(v) >= 25 else np.nan)
q = x.dropna(subset=["q"]).groupby(["T", "q"]).y7.mean().unstack(); sp = lad(q[0] - q[4]).dropna(); h = sp.index < CUT
print("   " + " ".join(f"Q{i+1} {lad(q[i]).mean()*100:+.2f}" for i in range(5)) + f" | Q1−Q5 {sp.mean()*100:+.2f}%/нед (t {nw_t(sp):.2f}; 1-я {sp[h].mean()*100:+.2f} / 2-я {sp[~h].mean()*100:+.2f})")
x["qr"] = x.groupby("T").rate7.transform(lambda v: pd.qcut(v.rank(method="first"), 5, labels=False) if len(v) >= 25 else np.nan)
hi = x[x.qr == 4]
print("   самая дорогая ставка (Q5) — по фандингу на фьючерсе: доход ШОРТА 7 суток с фандингом и комиссией")
for nm, cond in (("фандинг ≥ 0 (шорт не платит)", hi.f0 >= 0), ("фандинг 0…−0,03%/8 ч", (hi.f0 < 0) & (hi.f0 >= -0.0003)),
                 ("фандинг −0,03…−0,1%", (hi.f0 < -0.0003) & (hi.f0 >= -0.001)), ("фандинг < −0,1%", hi.f0 < -0.001)):
    g = hi[cond]; s = -g.y7 - 0.001; hh = g["T"] < CUT
    print(f"     {nm:30s} позиций {len(g):6d}: {s.mean()*100:+.2f}% (медиана {s.median()*100:+.2f}%, в плюсе {(s > 0).mean():.0%}; 1-я {s[hh].mean()*100:+.2f} / 2-я {s[~hh].mean()*100:+.2f})")
for N in (10,):
    S, t = short_top(dr, "spr", N)
    show(f"шорт 10 с наибольшим разрывом (без фандинга < −0,1%)", S); show("то же + лонг рынка", (S + mk.reindex(S.index)) / 2)
    hiq = x[(x.qr == 4) & (x.f0 >= -0.0003)]
    S2 = -hiq.groupby("T").y7.mean() - 0.001
    show("шорт всех Q5 по ставке с фандингом не дешевле −0,03%", S2); show("то же + лонг рынка", (S2 + mk.reindex(S2.index)) / 2)
print("\n# 2. Скачок ставки (×2 к медиане 60 суток, ≥ 0,03%/сут), монеты НЕТ в канале — ЛОНГ на 7 суток с фандингом и комиссией")
e = dr[(dr.rate0 >= 2 * dr.rate60m) & (dr.rate0 >= 0.0003) & (dr["T"] - dr.rate_first >= 60 * 86400)].sort_values(["s", "T"])
e = e[(e.s != e.s.shift()) | (e["T"] - e["T"].shift() > 7 * 86400)]
for nm, g in (("все", e), ("нет в канале", e[e.sh7 == 0]), ("в канале", e[e.sh7 > 0])):
    L = g.y7 - 0.001; hh = g["T"] < CUT
    top5 = L.nlargest(5).index
    print(f"   {nm:14s} событий {len(g):4d}: лонг {L.mean()*100:+.2f}% (медиана {L.median()*100:+.2f}%, в плюсе {(L > 0).mean():.0%}; "
          f"1-я {L[hh].mean()*100:+.2f} / 2-я {L[~hh].mean()*100:+.2f}; без 5 лучших {L.drop(top5).mean()*100:+.2f}%)")
base = dr[(dr.sh7 == 0)]; Lb = base.y7 - 0.001
print(f"   база: все дни монет вне канала — лонг {Lb.mean()*100:+.2f}% (медиана {Lb.median()*100:+.2f}%, в плюсе {(Lb > 0).mean():.0%})")
g = e[e.sh7 == 0].copy(); g["L"] = g.y7 - 0.001
print("   по месяцам (вне канала):", " ".join(f"{p}:{v*100:+.0f}({n})" for p, v, n in
      zip(*[pd.to_datetime(g["T"], unit="s").dt.to_period("Q").astype(str).pipe(lambda s: g.groupby(s).L.mean().index),
            g.groupby(pd.to_datetime(g["T"], unit="s").dt.to_period("Q").astype(str)).L.mean().values,
            g.groupby(pd.to_datetime(g["T"], unit="s").dt.to_period("Q").astype(str)).L.size().values])))
print("   крупнейшие:", ", ".join(f"{s} {datetime.datetime.utcfromtimestamp(T):%d.%m.%y} {L*100:+.0f}%" for s, T, L in g.nlargest(8, "L")[["s", "T", "L"]].values))
print("   худшие:", ", ".join(f"{s} {datetime.datetime.utcfromtimestamp(T):%d.%m.%y} {L*100:+.0f}%" for s, T, L in g.nsmallest(5, "L")[["s", "T", "L"]].values))
for h_ in (1, 3, 14):
    v = (g[f"ret{h_}"] - g[f"fr{h_}"] - 0.001).dropna()
    print(f"   горизонт {h_:2d} сут: лонг {v.mean()*100:+.2f}% (медиана {v.median()*100:+.2f}%, в плюсе {(v > 0).mean():.0%})")
