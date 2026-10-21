"""Разворот после роста: для каждого пампа месяца (+15% за ≤ 2 ч) — все 15-мин моменты в течение 24 ч после того,
как рост достиг +15%. Метка: падение на 15%+ от цены момента за следующие 24 ч (по минимуму свечей)."""
import pickle, datetime
import numpy as np
K = pickle.load(open("kaia/k15_all.pkl", "rb")); E = pickle.load(open("mm2/events.pkl", "rb"))
R = []; seen = set()
for s, i in E["памп"]:
    k = K[s]; h, l, c = k[:, 2], k[:, 3], k[:, 4]
    tp = next(j for j in range(i + 1, i + 9) if h[j] >= c[i] * 1.15)
    for m in range(tp, min(tp + 96, len(k) - 96)):
        if (s, m) in seen: continue
        seen.add((s, m))
        mn = l[m + 1:m + 97].min() / c[m] - 1; mx = h[m + 1:m + 97].max() / c[m] - 1
        pk = i + 1 + int(np.argmax(h[i + 1:m + 1]))
        R.append(dict(s=s, i=m, ev=(s, i), tp=tp, since_h=(m - tp) / 4, pump_gain=h[i + 1:m + 1].max() / c[i] - 1, gain_now=c[m] / c[i] - 1,
                      from_peak=c[m] / h[pk] - 1, h_since_peak=(m - pk) / 4, fwd_min=mn, fwd_max=mx, rev=mn <= -0.15))
print("моментов", len(R), "| пампов", len({r["ev"] for r in R}), "| с разворотом −15% за 24 ч:", sum(r["rev"] for r in R),
      f"({np.mean([r['rev'] for r in R]):.0%})", "| пампов, после которых был разворот:", len({r["ev"] for r in R if r["rev"]}))
pickle.dump(R, open("mm2/rev_moments.pkl", "wb"))
