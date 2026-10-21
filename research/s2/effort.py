"""«Усилие без результата» (Вайкофф): на 4-часовой границе объём за сутки ≥ X× среднего за неделю, а цена за сутки выросла
лишь на 0…Y% → шорт в закрытии. Одна сделка на монету за 48 ч. Комиссия 0,1%, фандинг по факту. Сравнение — тот же объём при падении."""
import pickle, datetime
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
P = pd.read_pickle("s2/panel_liq.pkl")
def trade(s, T, side, tp, sl, hold_h):
    a = K[s]; t = a["t"]; j = int(np.searchsorted(t, T - 900))
    if j >= len(t) or t[j] != T - 900: return None
    e = float(a["c"][j]); end = min(j + hold_h * 4, len(t) - 1)
    hi = a["h"][j + 1:end + 1].astype(np.float64); lo = a["l"][j + 1:end + 1].astype(np.float64)
    if side == "short": bad, good = np.flatnonzero(hi >= e * (1 + sl)), np.flatnonzero(lo <= e * (1 - tp))
    else: bad, good = np.flatnonzero(lo <= e * (1 - sl)), np.flatnonzero(hi >= e * (1 + tp))
    q1 = bad[0] if len(bad) else 10**9; q2 = good[0] if len(good) else 10**9
    if q1 <= q2 and q1 < 10**9: q = j + 1 + q1; px = -sl
    elif q2 < 10**9: q = j + 1 + q2; px = tp
    else: q = end; px = (1 - float(a["c"][end]) / e) if side == "short" else (float(a["c"][end]) / e - 1)
    fr = F.get(s); t_out = t[q] + 900; fund = 0.0
    if fr is not None:
        m = (fr[:, 0] > T) & (fr[:, 0] <= t_out); fund = fr[m, 2].sum() * (1 if side == "short" else -1)
    return px + fund - 0.001, fund
def events(cond, gap_h=48):
    E = P[cond].sort_values(["s", "t"]); out = []; last = {}
    for s, T in zip(E.s.values, E.t.values):
        if T - last.get(s, -10**12) >= gap_h * 3600: out.append((s, int(T))); last[s] = T
    return out
def report(name, ev, side, tp, sl, hold):
    res = [(T, *r) for s, T in ev if (r := trade(s, T, side, tp, sl, hold)) is not None]
    a = np.array(res); q = pd.to_datetime(a[:, 0], unit="s").to_period("Q").astype(str); df = pd.DataFrame({"q": q, "p": a[:, 1]})
    qm = df.groupby("q").p.mean()
    print(f"{name:52s} {side:5s} {tp:.0%}/{sl:.0%}/{hold}ч: {len(a):5d} | {a[:, 1].mean() * 100:+.2f}% | плюс {np.mean(a[:, 1] > 0):.0%} | фанд {a[:, 2].mean() * 100:+.2f}% | кв.+ {(qm > 0).sum()}/{len(qm)} | " +
          " ".join(f"{k[2:]}:{v * 100:+.1f}" for k, v in qm.items()))
for X in (3, 4, 6):
    for lo, hi in ((0, 0.1), (0.1, 0.25)):
        ev = events((P.volr >= X) & (P.r24 > lo) & (P.r24 <= hi))
        for tp, sl, hold in ((0.1, 0.15, 24), (0.15, 0.25, 48)):
            report(f"объём ≥ {X}×, рост за сутки {lo:.0%}–{hi:.0%}", ev, "short", tp, sl, hold)
ev = events((P.volr >= 4) & (P.r24 > -0.1) & (P.r24 <= 0)); report("для сравнения: объём ≥ 4×, падение 0–10%", ev, "short", 0.1, 0.15, 24)
