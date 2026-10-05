import pickle, numpy as np, pandas as pd
from sim import SIG, FUND, N, TAKER, MAKER, summ
PP = pickle.load(open("predpath.pkl", "rb")); SLIP = 0.002
def trade(s, tp, sl, rule=None, hold_h=48):
    e = s["entry"]; t, h, l, c, mh = s["t"], s["h"], s["l"], s["c"], s["mh"]
    n = min(hold_h * 60, len(t)); slp, tpp = e * (1 + sl / 100), (e * (1 - tp / 100) if tp else None)
    a = np.nonzero(mh[:n] >= slp)[0]; j_sl = a[0] if len(a) else n
    b = np.nonzero(l[:n] < tpp)[0] if tpp else []; j_tp = b[0] if len(b) else n
    j_fx = n
    if rule and (s["sym"], s["ep"]) in PP:
        pt, pr = PP[(s["sym"], s["ep"])]
        for i in range(len(pt)):
            jm = int((pt[i] - t[0]) // 60)
            if jm >= min(j_sl, j_tp, n): break
            if jm < 1: continue
            if rule(pr, i, c[jm - 1] / e - 1): j_fx = jm; break
    j = min(j_sl, j_tp, j_fx)
    if j == n: j = n - 1; px = c[j]; kind = "время"; fx = TAKER
    elif j == j_sl: px = slp * (1 + SLIP); kind = "стоп"; fx = TAKER
    elif j == j_tp: px = tpp; kind = "тейк"; fx = MAKER
    else: px = c[j - 1]; kind = "фандинг"; fx = TAKER
    xt = t[j] + 60; F = FUND.get(s["sym"]); fund = 0.0
    if F is not None:
        for ft, r in F[(F[:, 0] > t[0]) & (F[:, 0] <= xt)]:
            k = min(np.searchsorted(t, ft), len(c) - 1); fund += r * N * c[k] / e
    price = (1 - px / e) * N
    return dict(kind=kind, pnl=price + fund - N * TAKER - N * (px / e) * fx, fund=fund, xt=xt)
def run(tp, sl, rule=None):
    ou, ls, rows = {}, {}, []
    for s in SIG:
        if ou.get(s["sym"], 0) > s["ep"] or s["ep"] - ls.get(s["sym"], -1e18) < 48 * 3600: continue
        r = trade(s, tp, sl, rule); ou[s["sym"]] = r["xt"]
        if r["kind"] == "стоп": ls[s["sym"]] = r["xt"]
        rows.append(dict(ep=s["ep"], rule=s["rule"], **r))
    return pd.DataFrame(rows)
RULES = {"без досрочного выхода": None}
for X in (0.1, 0.2, 0.3, 0.5, 1.0): RULES[f"ставка ≤ −{X}%/ч"] = (lambda X: lambda pr, i, up: pr[i] <= -X / 100 * 100 if False else pr[i] <= -X)(X)
for D, w in ((0.05, 6), (0.1, 6), (0.2, 6), (0.1, 12), (0.2, 12)):
    RULES[f"упала на {D}%/ч за {w*5} мин"] = (lambda D, w: lambda pr, i, up: i >= w and pr[i] - pr[i - w] <= -D)(D, w)
for D, Y in ((0.05, 5), (0.1, 5), (0.05, 10), (0.1, 10)):
    RULES[f"упала на {D}%/ч за 30 мин и цена +{Y}%"] = (lambda D, Y: lambda pr, i, up: i >= 6 and pr[i] - pr[i - 6] <= -D and up >= Y / 100)(D, Y)
for X, Y in ((0.1, 10), (0.2, 10), (0.3, 5), (0.5, 5)):
    RULES[f"ставка ≤ −{X}%/ч и цена +{Y}%"] = (lambda X, Y: lambda pr, i, up: pr[i] <= -X and up >= Y / 100)(X, Y)
for tp, sl in ((6, 20), (15, 25)):
    print(f"\n===== {tp}/{sl} =====")
    for lab, rule in RULES.items():
        x = run(tp, sl, rule); vc = x.kind.value_counts()
        mid = x.ep.median()
        print(f"{lab:42s} итого {x.pnl.sum():+7.1f} (1-я пол. {x[x.ep<mid].pnl.sum():+5.1f} / 2-я {x[x.ep>=mid].pnl.sum():+5.1f}) | стопов {vc.get('стоп',0):3d}, досрочно {vc.get('фандинг',0):3d} | просадка {(x.pnl.cumsum()-x.pnl.cumsum().cummax()).min():+.1f}")
