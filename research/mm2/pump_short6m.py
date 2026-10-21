"""Шорт после пампа, причинное обнаружение (без заглядывания вперёд), 01.04–18.10.2026, 873 фьючерса.
Памп: в последние 2 ч была «спокойная» свеча i (|ret за 2 ч до неё| ≤ 5%), и после неё максимум достиг +15% от её закрытия.
Вход — закрытие свечи, где это случилось впервые (одна сделка на монету за 24 ч). Фандинг — фактический (до 30.09) или оценка по премии."""
import pickle, datetime, sys
import numpy as np
MSK = datetime.timezone(datetime.timedelta(hours=3))
K = pickle.load(open("kaia/k15_6m.pkl", "rb")); POS = pickle.load(open("kaia/positions.pkl", "rb")); PREM, FUND = POS["PREM"], POS["FUND"]
def fund_short(s, t_in, t_out):
    tot = 0.0; fu = FUND.get(s); p = PREM.get(s)
    last = fu[-1, 0] if fu is not None and len(fu) else 0
    if fu is not None:
        m = (fu[:, 0] > t_in) & (fu[:, 0] <= t_out); tot += fu[m, 2].sum()
    if t_out > last and p is not None:
        iv = int(fu[-1, 1]) if fu is not None and len(fu) else 8
        t = (int(max(t_in, last)) // (iv * 3600) + 1) * iv * 3600
        while t <= t_out:
            m = (p[:, 0] >= t - iv * 3600) & (p[:, 0] < t)
            if m.any():
                pr = p[m, 4].mean(); tot += float(np.clip((pr + np.clip(0.0001 - pr, -0.0005, 0.0005)) * iv / 8, -0.02, 0.02))
            t += iv * 3600
    return tot
def trade(k, j, tp, sl, hold):
    e = k[j, 4]
    for q in range(j + 1, min(j + 1 + hold, len(k))):
        if k[q, 2] >= e * (1 + sl): return -sl, k[q, 0] + 900
        if k[q, 3] <= e * (1 - tp): return tp, k[q, 0] + 900
    q = min(j + hold, len(k) - 1); return 1 - k[q, 4] / e, k[q, 0] + 900
def detect(k, thr=0.15):
    c, h = k[:, 4], k[:, 2]; n = len(k); out = []; last = -10**9
    calm = np.zeros(n, bool); calm[8:] = np.abs(c[8:] / c[:-8] - 1) <= 0.05
    for j in range(9, n - 1):
        if j - last < 96: continue
        lo = max(8, j - 8)
        base = [i for i in range(lo, j) if calm[i] and h[i + 1:j + 1].max() >= c[i] * (1 + thr)]
        if base: out.append((j, base[-1])); last = j
    return out
if __name__ == "__main__":
    EV = []
    for s, k in K.items():
        if len(k) < 200: continue
        for j, i in detect(k): EV.append((s, j, i))
    pickle.dump(EV, open("mm2/pumps6m.pkl", "wb"))
    print("пампов", len(EV), "у", len({e[0] for e in EV}), "монет")
    for tp, sl, hold in ((0.15, 0.15, 96), (0.15, 0.25, 192), (0.20, 0.25, 192)):
        rows = []
        for s, j, i in EV:
            k = K[s]
            if j + 2 >= len(k): continue
            pnl, t_out = trade(k, j, tp, sl, hold); t_in = k[j, 0] + 900
            rows.append((t_in, pnl - 0.001 + fund_short(s, t_in, t_out)))
        a = np.array(rows)
        print(f"\nтейк {tp:.0%} / стоп {sl:.0%} / {hold // 4} ч: сделок {len(a)}, итог {a[:, 1].mean():+.2%}, в плюсе {np.mean(a[:, 1] > 0):.0%}")
        for m in range(4, 11):
            t0 = datetime.datetime(2026, m, 1, tzinfo=MSK).timestamp(); t1 = datetime.datetime(2026 + (m == 12), m % 12 + 1, 1, tzinfo=MSK).timestamp()
            b = a[(a[:, 0] >= t0) & (a[:, 0] < t1), 1]
            print(f"  {m:02d}.2026: {len(b):4d} сделок, итог {b.mean():+.2%}, в плюсе {np.mean(b > 0):.0%}")
