"""Лонг «откуп в коридоре»: монета анти-устойчива (VR за 7 суток до движения ≤ порога), цена за 4 ч упала на ≥ X% → лонг в закрытии.
Одна сделка на монету за 24 ч. Комиссия 0,1%, фандинг по факту. Отдельно — без общих обвалов (BTC за те же 4 ч −3% и хуже)."""
import pickle, datetime
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
UTC = datetime.timezone.utc
B = K["BTC"]; btc = {int(t): float(c) for t, c in zip(B["t"], B["c"])}
def roll(x, w):
    cs = np.concatenate([[0.0], np.cumsum(x, dtype=np.float64)]); out = np.full(len(x), np.nan); out[w - 1:] = cs[w:] - cs[:-w]; return out
PRE = {}
for s, a in K.items():
    c = a["c"].astype(np.float64); n = len(c)
    if n < 2000: continue
    r = np.zeros(n); r[1:] = np.diff(np.log(c)); W = 672
    s1, s2 = roll(r, W), roll(r * r, W); var1 = (s2 - s1 ** 2 / W) / (W - 1)
    r16 = np.zeros(n); r16[16:] = np.log(c[16:] / c[:-16]); p1, p2 = roll(r16, W - 15), roll(r16 * r16, W - 15); var16 = (p2 - p1 ** 2 / (W - 15)) / (W - 16)
    with np.errstate(invalid="ignore", divide="ignore"): vr16 = var16 / (16 * var1)
    mv = np.full(n, np.nan); mv[16:] = c[16:] / c[:-16] - 1
    PRE[s] = (vr16, mv, roll(a["qv"].astype(np.float64), 96))
def trade(s, j, tp, sl, hold):
    a = K[s]; t = a["t"]; e = float(a["c"][j]); end = min(j + hold, len(t) - 1)
    lo = a["l"][j + 1:end + 1].astype(np.float64); hi = a["h"][j + 1:end + 1].astype(np.float64)
    bad, good = np.flatnonzero(lo <= e * (1 - sl)), np.flatnonzero(hi >= e * (1 + tp))
    q1 = bad[0] if len(bad) else 10**9; q2 = good[0] if len(good) else 10**9
    if q1 <= q2 and q1 < 10**9: q = j + 1 + q1; px = -sl
    elif q2 < 10**9: q = j + 1 + q2; px = tp
    else: q = end; px = float(a["c"][end]) / e - 1
    fr = F.get(s); t_in = t[j] + 900; t_out = t[q] + 900; fund = 0.0
    if fr is not None:
        m = (fr[:, 0] > t_in) & (fr[:, 0] <= t_out); fund = -float(fr[m, 2].sum())
    return t_in, px + fund - 0.001
def events(vr_max, drop, drop_max=0.5, vmin=3e6):
    out = []
    for s, (vr16, mv, v24) in PRE.items():
        t = K[s]["t"]; last = -10**9
        for j in np.flatnonzero((mv <= -drop) & (mv > -drop_max)):
            if j < 700 or j + 2 >= len(t) or j - last < 96 or v24[j] < vmin: continue
            if not (vr16[j - 16] <= vr_max): continue
            last = j; b0, b1 = btc.get(int(t[j - 16])), btc.get(int(t[j]))
            out.append((s, int(j), (b1 / b0 - 1) if b0 and b1 else np.nan))
    return out
if __name__ == "__main__":
    res = []
    for vr_max in (0.6, 0.7, 0.8):
        for drop in (0.05, 0.08, 0.12):
            ev = events(vr_max, drop)
            for tp, sl, hold in ((0.05, 0.05, 96), (0.08, 0.08, 96), (0.1, 0.15, 192)):
                d = pd.DataFrame([(s, *trade(s, j, tp, sl, hold), b) for s, j, b in ev], columns=["s", "t", "p", "btc4"])
                d["q"] = pd.to_datetime(d.t, unit="s").dt.to_period("Q").astype(str); qm = d.groupby("q").p.mean()
                nc = d[~(d.btc4 <= -0.03)]
                res.append((vr_max, f"{drop:.0%}", f"{tp:.0%}/{sl:.0%}/{hold // 4}ч", len(d), d.s.nunique(), round(d.p.mean() * 100, 2), round((d.p > 0).mean() * 100),
                            f"{(qm > 0).sum()}/{len(qm)}", round(nc.p.mean() * 100, 2), " ".join(f"{k[2:]}:{v * 100:+.1f}" for k, v in qm.items())))
    pd.set_option("display.width", 320)
    print(pd.DataFrame(res, columns=["VR ≤", "падение", "выход", "сделок", "монет", "итог %", "в плюсе %", "кв.+", "без обвалов BTC", "по кварталам"]).to_string(index=False))
