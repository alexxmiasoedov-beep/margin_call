"""Лонг на продолжение пампа у монет «только фьючерс» без корейской/турецкой розницы. Вход в момент пампа, разные выходы."""
import pickle, datetime
import numpy as np, pandas as pd
EV = pickle.load(open("mm2/pumps2y.pkl", "rb"))["EV"]; F = pickle.load(open("s2/fund2y.pkl", "rb"))
D = pd.read_pickle("s3/pump_spot.pkl")
def lng(w, j, tp, sl, hold):
    e = w[j, 3]
    for q in range(j + 1, min(j + 1 + hold, len(w))):
        if w[q, 2] <= e * (1 - sl): return -sl, w[q, 0] + 900
        if w[q, 1] >= e * (1 + tp): return tp, w[q, 0] + 900
    q = min(j + hold, len(w) - 1); return w[q, 3] / e - 1, w[q, 0] + 900
other = (~(D.korea & (D.kshare >= 0.2)) & ~(D.tshare >= 0.1)).values; po = (~D.spot).values
res = []
for tp, sl, hold in ((0.1, 0.05, 8), (0.1, 0.1, 24), (0.15, 0.1, 48), (0.2, 0.1, 96), (0.25, 0.15, 192), (0.3, 0.2, 192)):
    for lab, mask in (("только фьючерс, без розницы", po & other), ("есть спот (для сравнения)", ~po)):
        rows = []
        for k in np.flatnonzero(mask):
            e = EV[k]; px, t_out = lng(e["w"], e["j"], tp, sl, hold); fr = F.get(e["s"]); fund = 0.0
            if fr is not None:
                m = (fr[:, 0] > e["t_in"]) & (fr[:, 0] <= t_out); fund = -float(fr[m, 2].sum())
            rows.append((e["t_in"], px + fund - 0.001, fund))
        a = pd.DataFrame(rows, columns=["t", "p", "fund"]); a["q"] = pd.to_datetime(a.t, unit="s").dt.to_period("Q").astype(str); qm = a.groupby("q").p.mean()
        res.append((lab, f"{tp:.0%}/{sl:.0%}/{hold // 4}ч", len(a), round(a.p.mean() * 100, 2), round((a.p > 0).mean() * 100), round(a.fund.mean() * 100, 2), f"{(qm > 0).sum()}/{len(qm)}",
                    " ".join(f"{k[2:]}:{v * 100:+.1f}" for k, v in qm.items())))
pd.set_option("display.width", 300)
print(pd.DataFrame(res, columns=["группа", "выход", "сделок", "лонг %", "в плюсе %", "фанд %", "кв.+", "по кварталам"]).to_string(index=False))
