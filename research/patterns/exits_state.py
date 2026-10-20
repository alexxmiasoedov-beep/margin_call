"""Бэктест вариантов выхода для шортов бота в состоянии «премия < −4% и фандинг ≤ −1% за сутки до сигнала».
Сигналы — signals_scan_full.pkl (логика бота, 23.02.2025–15.10.2026). Вход — open минуты сигнала, стоп по марк-цене +0,2%,
тейк лимитный (мейкер), фандинг по факту (октябрь — оценка), одна позиция на монету, пауза 48 ч после стопа."""
import pickle, datetime
import numpy as np, pandas as pd
UTC = datetime.timezone.utc
D = pickle.load(open("signals_scan_full.pkl", "rb")); SIG = sorted(D["sig"], key=lambda s: s["ep"]); FUND = D["fund"]
PREM = pickle.load(open("kaia/prem_sig.pkl", "rb"))
N, TAKER, MAKER = 10.0, 0.0005, 0.0002
CUT = datetime.datetime(2026, 9, 28, tzinfo=UTC).timestamp()
for s in SIG:
    te = s["te"]; p = PREM.get(s["sym"]); f = FUND.get(s["sym"])
    w = p[(p[:, 0] >= te - 86400) & (p[:, 0] < te)] if p is not None else None
    s["pm"] = w[:, 4].min() * 100 if w is not None and len(w) >= 40 else np.nan
    g = f[(f[:, 0] > te - 86400) & (f[:, 0] <= te)] if f is not None and len(f) else None
    s["fm"] = g[:, 1].min() * 100 if g is not None and len(g) else np.nan
    s["state"] = bool(s["pm"] < -4 and s["fm"] <= -1)
def trade(s, tp, sl, hold_h=48, before=None, slip=0.002):
    e = s["entry"]; t, l, c, mh = s["t"], s["l"], s["c"], s["mh"]
    n = min(int(hold_h * 60), len(t))
    F = FUND.get(s["sym"])
    if before and F is not None and len(F):
        fut = F[F[:, 0] > s["te"], 0]
        if len(fut) >= before: n = min(n, max(1, int((fut[before - 1] - 60 - s["te"]) // 60)))
    if n < 1: return None
    slp, tpp = e * (1 + sl / 100), (e * (1 - tp / 100) if tp else None)
    a = np.flatnonzero(mh[:n] >= slp); j_sl = a[0] if len(a) else n
    b = np.flatnonzero(l[:n] < tpp) if tpp else []; j_tp = b[0] if len(b) else n
    j = min(j_sl, j_tp)
    if j == n: j = n - 1; px = c[j]; kind = "время"; fx = TAKER
    elif j == j_sl: px = slp * (1 + slip); kind = "стоп"; fx = TAKER
    else: px = tpp; kind = "тейк"; fx = MAKER
    xt = t[j] + 60; fund = 0.0
    if F is not None and len(F):
        for ft, r in F[(F[:, 0] > s["te"]) & (F[:, 0] <= xt)]:
            k = min(np.searchsorted(t, ft), len(c) - 1); fund += r * N * (c[k] / e)
    price = (1 - px / e) * N; fee = N * TAKER + N * (px / e) * fx
    return dict(kind=kind, price=price, fund=fund, pnl=price + fund - fee, xt=xt, hours=(xt - s["te"]) / 3600)
def run(var_state, var_other=(15, 25, 48, None), t_to=CUT):
    ou, ls, rows = {}, {}, []
    for s in SIG:
        if s["ep"] >= t_to: continue
        if ou.get(s["sym"], 0) > s["ep"] or s["ep"] - ls.get(s["sym"], -1e18) < 48 * 3600: continue
        tp, sl, hold, before = var_state if s["state"] else var_other
        r = trade(s, tp, sl, hold, before)
        if r is None: continue
        ou[s["sym"]] = r["xt"]
        if r["kind"] == "стоп": ls[s["sym"]] = r["xt"]
        rows.append(dict(ep=s["ep"], sym=s["sym"], state=s["state"], **r))
    return pd.DataFrame(rows)
print(f"сигналов до 27.09.2026: {sum(s['ep'] < CUT for s in SIG)}, из них в состоянии: {sum(s['state'] and s['ep'] < CUT for s in SIG)}")
V = [("как сейчас: 15/25, 48 ч", (15, 25, 48, None)), ("15/25, 24 ч", (15, 25, 24, None)), ("15/25, 12 ч", (15, 25, 12, None)),
     ("15/25, 8 ч", (15, 25, 8, None)), ("15/25, 4 ч", (15, 25, 4, None)), ("3/25, 48 ч", (3, 25, 48, None)), ("4/25, 48 ч", (4, 25, 48, None)),
     ("5/25, 48 ч", (5, 25, 48, None)), ("6/25, 48 ч", (6, 25, 48, None)), ("8/25, 48 ч", (8, 25, 48, None)), ("10/25, 48 ч", (10, 25, 48, None)),
     ("6/20, 48 ч", (6, 20, 48, None)), ("15/20, 48 ч", (15, 20, 48, None)), ("10/25, 12 ч", (10, 25, 12, None)),
     ("15/25, выход перед 1-м фандингом", (15, 25, 48, 1)), ("15/25, выход перед 2-м фандингом", (15, 25, 48, 2)),
     ("6/25, выход перед 1-м фандингом", (6, 25, 48, 1))]
base = run(V[0][1])
rows = []
for name, v in V:
    x = run(v); st = x[x.state]; y25 = st[st.ep < datetime.datetime(2026, 1, 1, tzinfo=UTC).timestamp()]; y26 = st[st.ep >= datetime.datetime(2026, 1, 1, tzinfo=UTC).timestamp()]
    vc = st.kind.value_counts(normalize=True) * 100
    rows.append({"вариант для шортов в состоянии": name, "сделок": len(st), "тейк%": round(vc.get("тейк", 0)), "стоп%": round(vc.get("стоп", 0)),
                 "часов": round(st.hours.mean(), 1), "цена": round(st.price.sum(), 1), "фандинг": round(st.fund.sum(), 1), "итог": round(st.pnl.sum(), 1),
                 "на сделку": round(st.pnl.mean(), 3), "2025": round(y25.pnl.sum(), 1), "2026": round(y26.pnl.sum(), 1),
                 "весь портфель": round(x.pnl.sum(), 1)})
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 20)
print(pd.DataFrame(rows).to_string(index=False))
ns = base[~base.state]
print(f"\nдля сравнения — сигналы вне состояния при 15/25, 48 ч: {len(ns)} сделок, итог {ns.pnl.sum():+.1f}, на сделку {ns.pnl.mean():+.3f}, фандинг {ns.fund.sum():+.1f}")
pickle.dump(dict(rows=rows), open("kaia/exits_state_res.pkl", "wb"))
