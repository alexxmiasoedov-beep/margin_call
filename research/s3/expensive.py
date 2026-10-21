"""Лонг после пампа у «дорогих» монет (номинальная цена ≥ X $): вход в момент пампа (как в корейском бэктесте), выход по тейку/стопу/времени.
Группы: все, без Кореи (нет на Upbit/Bithumb или доля < 5%), без турецкой доли. Комиссия 0,1%, фандинг по факту."""
import pickle, datetime
import numpy as np, pandas as pd
EV = pickle.load(open("mm2/pumps2y.pkl", "rb"))["EV"]; R = pickle.load(open("mm2/bt2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
TR = pd.read_pickle("s2/pump_TRY.pkl")
def lng(w, j, tp, sl, hold):
    e = w[j, 3]
    for q in range(j + 1, min(j + 1 + hold, len(w))):
        if w[q, 2] <= e * (1 - sl): return -sl, w[q, 0] + 900
        if w[q, 1] >= e * (1 + tp): return tp, w[q, 0] + 900
    q = min(j + hold, len(w) - 1); return w[q, 3] / e - 1, w[q, 0] + 900
rows = []
for e, r, tr in zip(EV, R, TR.itertuples()):
    w, j = e["w"], e["j"]; price = w[j, 3]
    for tp, sl, hold in ((0.10, 0.05, 8), (0.15, 0.07, 24), (0.20, 0.10, 96), (0.30, 0.15, 192)):
        px, t_out = lng(w, j, tp, sl, hold); fr = F.get(e["s"]); fund = 0.0
        if fr is not None:
            m = (fr[:, 0] > e["t_in"]) & (fr[:, 0] <= t_out); fund = -float(fr[m, 2].sum())
        rows.append(dict(s=e["s"], t=e["t_in"], price=price, korea=r["korea"], kshare=r["share"], tshare=tr.fshare, exit=f"{tp:.0%}/{sl:.0%}/{hold // 4}ч", p=px + fund - 0.001))
D = pd.DataFrame(rows); D["q"] = pd.to_datetime(D.t, unit="s").dt.to_period("Q").astype(str)
D["noretail"] = (~D.korea | (D.kshare < 0.05)) & ~(D.tshare >= 0.03)
for ex in D.exit.unique():
    print(f"\n=== лонг после пампа, выход {ex}")
    for lab, m in (("все пампы", D.price > 0), ("цена ≥ 1 $", D.price >= 1), ("цена ≥ 5 $", D.price >= 5), ("цена ≥ 1 $ и без розницы (KR < 5%, TRY < 3%)", (D.price >= 1) & D.noretail),
                   ("цена < 0,01 $", D.price < 0.01)):
        d = D[(D.exit == ex) & m]; qm = d.groupby("q").p.mean()
        print(f"{lab:46s} {len(d):5d} | {d.p.mean() * 100:+.2f}% | плюс {(d.p > 0).mean():.0%} | кв.+ {(qm > 0).sum()}/{len(qm)} | " + " ".join(f"{k[2:]}:{v * 100:+.1f}" for k, v in qm.items()))
