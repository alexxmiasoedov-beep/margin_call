"""Доля тайской розницы (Bitkub, бат) в объёме за час на момент пампа (как доля Кореи в корейском шорте); шорт 10/25/48 ч по группам."""
import pickle, datetime
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb")); TH = pickle.load(open("s4/thai.pkl", "rb")); P = pd.read_pickle("s2/pump_TRY.pkl")
UTC = datetime.timezone.utc; CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp()
th = []
for x in P.itertuples():
    if x.s not in TH: th.append(np.nan); continue
    v, first = TH[x.s]
    if first > x.t - 7 * 86400: th.append(np.nan); continue          # пара на Bitkub должна торговаться хотя бы неделю до пампа
    t = K[x.s]["t"]; j = np.searchsorted(t, x.t - 900)
    th.append(float(v[j - 3:j + 1].sum()))
P["thai"] = th; P["thas"] = P.thai.notna(); P["tshare"] = P.thai / (P.thai + P.fut); P["y"] = np.where(P.t < CUT, 1, 2)
P.to_pickle("s4/pump_THB.pkl")
def show(nm, m):
    d = P[m]; print(f"{nm:58s} {len(d):5d} | шорт {d.pnl.mean()*100:+.2f}% | 1-й год {d[d.y==1].pnl.mean()*100:+.2f} ({(d.y==1).sum()}) | 2-й год {d[d.y==2].pnl.mean()*100:+.2f} ({(d.y==2).sum()}) | в плюсе {(d.pnl>0).mean():.0%}")
print(f"пампов с парой к бату: {P.thas.sum()} из {len(P)}; доля бата: медиана {P.tshare.median():.2%}, 90-й перц. {P.tshare.quantile(.9):.2%}")
show("все пампы", P.y > 0); show("есть пара к бату", P.thas); show("нет пары к бату", ~P.thas)
for lo, hi in ((0, 0.005), (0.005, 0.02), (0.02, 0.05), (0.05, 0.1), (0.1, 0.2), (0.2, 1)):
    show(f"доля бата {lo:.1%}–{hi:.1%}", P.thas & (P.tshare >= lo) & (P.tshare < hi))
noKT = ~(P.korea & (P.kshare >= 0.2)) & ~(P.has & (P.fshare >= 0.1))
print("--- без корейского шорта (доля Кореи < 20%) и без турецкой доли ≥ 10%:")
for lo, hi in ((0, 0.005), (0.005, 0.02), (0.02, 0.05), (0.05, 0.1), (0.1, 1)):
    show(f"доля бата {lo:.1%}–{hi:.1%}", noKT & P.thas & (P.tshare >= lo) & (P.tshare < hi))
