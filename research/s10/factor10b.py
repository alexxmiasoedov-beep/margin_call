"""Базовый топ-10 по займам (отбор по всему рынку) и ончейн-отток как дополнительное условие: по подпериодам."""
import datetime
import numpy as np, pandas as pd
exec(open("s10/factor10.py").read().split("o = d[d.dq.notna()]")[0])
MID = datetime.datetime(2026, 4, 15, tzinfo=datetime.timezone.utc).timestamp()
pool = d[(d.sh7 > 0) & ~(d.f0 < -0.001)]
top = pool.assign(rr=pool.groupby("T").sh7.rank(ascending=False, method="first")).query("rr <= 10").copy()
top["sp"] = -top.y7
per = np.select([top["T"] < CUT, top["T"] < MID], ["до 12.2025", "12.2025–04.2026"], "после 15.04.2026")
top["per"] = per
top["g"] = pd.cut(top.dq, [-np.inf, -0.05, -0.01, 0.01, 0.05, np.inf], labels=["отток >5%", "отток 1–5%", "±1%", "приток 1–5%", "приток >5%"]).astype(str)
top.loc[top.dq.isna(), "g"] = "нет данных"
T = top.groupby(["g", "per"]).sp.agg(["mean", "size"]).unstack()
print("Доход шорта 7 дн с фандингом (без комиссии), %, и число позиций — базовый топ-10, по изменению баланса Binance за неделю:")
for g in ["отток >5%", "отток 1–5%", "±1%", "приток 1–5%", "приток >5%", "нет данных"]:
    print(f"   {g:12s} " + "  ".join(f"{p}: {T.loc[g, ('mean', p)]*100:+6.2f} ({T.loc[g, ('size', p)]:.0f})" for p in ["до 12.2025", "12.2025–04.2026", "после 15.04.2026"]))
# сколько разных монет и эпизодов в группе «отток >5%»
x = top[top.g == "отток >5%"]
print(f"\n«отток >5%»: монет {x.s.nunique()}, позиций {len(x)}; крупнейший вклад:")
c = x.groupby("s").sp.agg(["sum", "size", "mean"]).sort_values("sum", ascending=False)
print("   " + "; ".join(f"{s} {r['sum']*100:+.0f}% ({r['size']:.0f} поз.)" for s, r in c.head(8).iterrows()))
print("   худшие: " + "; ".join(f"{s} {r['sum']*100:+.0f}% ({r['size']:.0f})" for s, r in c.tail(5).iterrows()))
print(f"   без 3 лучших монет: {x[~x.s.isin(c.index[:3])].sp.mean()*100:+.2f}% на позицию")
# эпизоды: склеиваем подряд идущие дни одной монеты
x = x.sort_values(["s", "T"]); ep = (x.s != x.s.shift()) | (x["T"] - x["T"].shift() > 3 * 86400)
x["ep"] = ep.cumsum(); e = x.groupby("ep").agg(s=("s", "first"), T=("T", "first"), sp=("sp", "first"))
print(f"   эпизодов (подряд идущие дни склеены): {len(e)}, доход шорта по первому дню эпизода {e.sp.mean()*100:+.2f}% (медиана {e.sp.median()*100:+.2f}%), в плюсе {(e.sp > 0).mean():.0%}")
y = top[top.g.isin(["отток 1–5%", "±1%", "приток 1–5%", "приток >5%"])].sort_values(["s", "T"])
ep = (y.s != y.s.shift()) | (y["T"] - y["T"].shift() > 3 * 86400); y["ep"] = ep.cumsum()
e2 = y.groupby("ep").agg(sp=("sp", "first"))
print(f"   для сравнения, остальные с данными: эпизодов {len(e2)}, доход {e2.sp.mean()*100:+.2f}% (медиана {e2.sp.median()*100:+.2f}%), в плюсе {(e2.sp > 0).mean():.0%}")
