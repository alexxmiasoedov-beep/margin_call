"""Новые бессрочные фьючерсы Binance (первая свеча 2024-10-19 … 2026-09-18): шорт через D суток после листинга, выход по тейку/стопу
или через H суток. Комиссия 0,1%, фандинг по факту из архива (шорт получает положительный, платит отрицательный)."""
import pickle, datetime
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
UTC = datetime.timezone.utc
A = datetime.datetime(2024, 10, 19, tzinfo=UTC).timestamp(); Bd = datetime.datetime(2026, 9, 18, tzinfo=UTC).timestamp()
def fund(s, a, b):
    fr = F.get(s)
    if fr is None: return 0.0
    m = (fr[:, 0] > a) & (fr[:, 0] <= b); return float(fr[m, 2].sum())
def short(s, j, tp, sl, hold):
    a = K[s]; e = float(a["c"][j]); n = len(a["t"]); end = min(j + hold, n - 1)
    hi = a["h"][j + 1:end + 1].astype(np.float64); lo = a["l"][j + 1:end + 1].astype(np.float64)
    ks = np.flatnonzero(hi >= e * (1 + sl)); kt = np.flatnonzero(lo <= e * (1 - tp)) if tp else np.array([], int)
    q1 = ks[0] if len(ks) else 10**9; q2 = kt[0] if len(kt) else 10**9
    if q1 <= q2 and q1 < 10**9: q = j + 1 + q1; pnl = -sl
    elif q2 < 10**9: q = j + 1 + q2; pnl = tp
    else: q = end; pnl = 1 - float(a["c"][end]) / e
    t_in = a["t"][j] + 900; t_out = a["t"][q] + 900
    return pnl - 0.001 + fund(s, t_in, t_out), (t_out - t_in) / 86400
new = [(s, a["t"][0]) for s, a in K.items() if A <= a["t"][0] <= Bd]
print("новых листингов:", len(new))
rows = []
for D in (0.5, 1, 3, 7):
    for tp, sl, H in ((None, 0.5, 14), (0.3, 0.3, 14), (0.2, 0.25, 7), (0.5, 0.5, 30)):
        res = []
        for s, t0 in new:
            j = int(D * 96)
            if j + 2 >= len(K[s]["t"]): continue
            pnl, days = short(s, j, tp, sl, int(H * 96)); res.append((t0, pnl, days))
        r = np.array(res); yr = pd.to_datetime(r[:, 0], unit="s").year
        rows.append((D, f"{'без' if tp is None else f'{tp:.0%}'}/{sl:.0%}/{H} дн", len(r), round(r[:, 1].mean() * 100, 2), round(np.median(r[:, 1]) * 100, 2),
                     round((r[:, 1] > 0).mean() * 100), round(r[:, 2].mean(), 1), " ".join(f"{y}:{r[yr == y, 1].mean() * 100:+.1f}({(yr == y).sum()})" for y in (2024, 2025, 2026))))
print(pd.DataFrame(rows, columns=["вход через, сут", "тейк/стоп/срок", "сделок", "средний %", "медиана %", "в плюсе %", "дней", "по годам"]).to_string(index=False))
