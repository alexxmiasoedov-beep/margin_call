"""Паника турецкой розницы: доля пары к лире за час ≥ S и в M раз выше обычной, а цена фьючерса за 4 ч упала на 5…40% → ЛОНГ.
Одна сделка на монету за 48 ч, комиссия 0,1%, фандинг по факту (лонг получает отрицательный)."""
import numpy as np, pandas as pd
exec(open("s2/rush.py").read().split("def trade(s, j, tp, sl, hold):")[0])
def trade_long(s, j, tp, sl, hold):
    a = K[s]; t = a["t"]; e = float(a["c"][j]); end = min(j + hold, len(t) - 1)
    hi = a["h"][j + 1:end + 1].astype(np.float64); lo = a["l"][j + 1:end + 1].astype(np.float64)
    bad, good = np.flatnonzero(lo <= e * (1 - sl)), np.flatnonzero(hi >= e * (1 + tp))
    q1 = bad[0] if len(bad) else 10**9; q2 = good[0] if len(good) else 10**9
    if q1 <= q2 and q1 < 10**9: q = j + 1 + q1; px = -sl
    elif q2 < 10**9: q = j + 1 + q2; px = tp
    else: q = end; px = float(a["c"][end]) / e - 1
    fr = F.get(s); t_in = t[j] + 900; t_out = t[q] + 900; fund = 0.0
    if fr is not None:
        m = (fr[:, 0] > t_in) & (fr[:, 0] <= t_out); fund = -float(fr[m, 2].sum())
    return t_in, px + fund - 0.001
res = []
for S, M in ((0.05, 3), (0.1, 3), (0.1, 5), (0.2, 3)):
    for lo, hi in ((-0.4, -0.15), (-0.4, -0.10), (-0.10, -0.05)):
        ev = events(S, M, lo, hi)
        if len(ev) < 30: continue
        for tp, sl, hold in ((0.1, 0.1, 96), (0.15, 0.15, 192)):
            d = pd.DataFrame([(s, *trade_long(s, j, tp, sl, hold)) for s, j in ev], columns=["s", "t", "p"])
            d["q"] = pd.to_datetime(d.t, unit="s").dt.to_period("Q").astype(str); qm = d.groupby("q").p.mean()
            res.append((S, M, f"{lo:+.0%}…{hi:+.0%}", f"{tp:.0%}/{sl:.0%}/{hold // 4}ч", len(d), round(d.p.mean() * 100, 2), round((d.p > 0).mean() * 100),
                        f"{(qm > 0).sum()}/{len(qm)}", " ".join(f"{k[2:]}:{v * 100:+.1f}" for k, v in qm.items())))
pd.set_option("display.width", 300)
print(pd.DataFrame(res, columns=["доля ≥", "×", "цена за 4 ч", "выход", "сделок", "лонг %", "в плюсе %", "кв.+", "по кварталам"]).to_string(index=False))
