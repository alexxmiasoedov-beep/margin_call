"""Фон для «слабого старта листинга»: тот же шорт (30/40/21 дн. и 30/30/14 дн.) у обычных монет (возраст > 60 дней, объём ≥ 3 млн $),
вход 1-го и 15-го числа каждого месяца в 00:00 UTC; и у новых листингов без слабого старта. По годам."""
import pickle, datetime
import numpy as np, pandas as pd
exec(open("s3/newlist2.py").read().split("rows = []")[0])
starts = [datetime.datetime(y, m, d, tzinfo=UTC).timestamp() for y in (2024, 2025, 2026) for m in range(1, 13) for d in (1, 15)]
starts = [x for x in starts if A <= x <= Bd]
for tp, sl, hold in ((0.3, 0.4, 21), (0.3, 0.3, 14)):
    rows = []
    for s, a in K.items():
        t = a["t"]; qv = a["qv"].astype(np.float64)
        for T in starts:
            j = int(np.searchsorted(t, T - 900))
            if j >= len(t) - 2 or t[j] != T - 900 or (T - t[0]) < 60 * 86400 or qv[max(0, j - 95):j + 1].sum() < 3e6: continue
            rows.append((T, short(s, j, tp, sl, hold * 96)))
    d = pd.DataFrame(rows, columns=["t", "p"]); d["y"] = np.where(d.t < CUT, 1, 2)
    print(f"фон, обычные монеты, шорт {tp:.0%}/{sl:.0%}/{hold} дн.: {len(d)} сделок, {d.p.mean() * 100:+.2f}% (1-й год {d[d.y == 1].p.mean() * 100:+.2f}, 2-й {d[d.y == 2].p.mean() * 100:+.2f}), в плюсе {(d.p > 0).mean():.0%}")
    for X in (0.25,):
        w, sgood = [], []
        for s, a in K.items():
            if not (A <= a["t"][0] <= Bd) or len(a["t"]) < 96 * 16: continue
            j = 96; weak = float(a["c"][j]) <= a["h"][:j + 1].max() * (1 - X)
            (w if weak else sgood).append((a["t"][0], short(s, j, tp, sl, hold * 96)))
        for lab, L in (("новые листинги со слабым стартом", w), ("новые листинги без слабого старта", sgood)):
            d = pd.DataFrame(L, columns=["t", "p"]); d["y"] = np.where(d.t < CUT, 1, 2)
            print(f"   {lab}: {len(d)}, {d.p.mean() * 100:+.2f}% (1-й год {d[d.y == 1].p.mean() * 100:+.2f}, 2-й {d[d.y == 2].p.mean() * 100:+.2f})")
