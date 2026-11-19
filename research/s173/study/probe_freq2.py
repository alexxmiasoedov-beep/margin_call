"""s173 — частота вариантов H2 (выбор площадки), H3 (памп +10%) и H6 (след хеджа перед разлоком), без доходов.
Запуск: python3 -I probe_freq2.py <папка данных>"""
import os
import pickle
import sys
from collections import Counter

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_freq import NONCRYPTO, hourly, month, roll_sum  # noqa: E402

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"


def per_month(ts):
    if not len(ts):
        return "нет событий"
    m = pd.Series([month(np.int64(t)) for t in ts]).value_counts().sort_index()
    full = m.iloc[1:-1] if len(m) > 3 else m
    return f"{len(ts)} всего, в месяц медиана {full.median():.1f}, среднее {full.mean():.1f}"


with open(os.path.join(D, "s2/k2y.pkl"), "rb") as f:
    K = pickle.load(f)
kind = pd.read_pickle(os.path.join(D, "s12/perp_kind.pkl"))
BAD = set(kind.get("tradfi", set())) | NONCRYPTO
sp = pd.read_pickle(os.path.join(D, "s23/spot1h.pkl"))
F = pd.read_pickle(os.path.join(D, "s2/fund2y.pkl"))

h2a, h2b, h3 = [], [], Counter()
daily_rank_pool = Counter()
HX = {}
for s in K:
    if s in BAD or s.endswith("USDC"):
        continue
    T, x = hourly(K[s])
    if len(T) < 24 * 40:
        continue
    HX[s] = (T, x)
    c, qv, tb, lo, hi = x["c"], x["qv"], x["tb"], x["lo"], x["hi"]
    v24 = roll_sum(qv, 24)
    # H3: памп +10% за ≤ 2 ч из покоя (диапазон предыдущих 24 ч ≤ 8%)
    lo2 = np.minimum(lo, np.r_[lo[0], lo[:-1]])
    rng = (pd.Series(hi).shift(2).rolling(24, min_periods=24).max() /
           pd.Series(lo).shift(2).rolling(24, min_periods=24).min() - 1).values
    for thr in (0.10, 0.15):
        cand = np.flatnonzero((c / lo2 - 1 >= thr) & (v24 >= 2e6) & (rng <= 0.08))
        last = -10 ** 9
        for i in cand:
            if i - last >= 24:
                last = i; h3[(thr, str(month(np.int64(T[i]))))] += 1
    # H2: перп/спот ×2 к норме, ход ≤ ±3%, доля агрессивных покупок перпа за 24 ч ≤ 48%
    if s in sp:
        a = np.asarray(sp[s])
        Hs = a[:, 0].astype(np.int64) // 3600
        sq = np.zeros(len(T)); m_ = (Hs >= T[0]) & (Hs <= T[-1])
        sq[(Hs[m_] - T[0]).astype(int)] = a[m_, 1]
        s24 = roll_sum(sq, 24)
        tb24 = roll_sum(tb, 24)
        with np.errstate(divide="ignore", invalid="ignore"):
            lps = np.log(v24 / s24)
            bs = tb24 / v24
        last = -10 ** 9
        for i in np.flatnonzero(T % 24 == 0):
            if i < 24 * 31 or v24[i] < 5e6 or s24[i] <= 0 or not np.isfinite(lps[i]):
                continue
            hist = lps[i - 24 * 30:i - 24:24]
            hist = hist[np.isfinite(hist)]
            if len(hist) < 20:
                continue
            z = lps[i] - np.median(hist)
            daily_rank_pool[T[i] // 24] += 1
            if abs(c[i] / c[i - 24] - 1) > 0.03 or i - last < 24 * 7:
                continue
            if z >= np.log(2):
                h2a.append(T[i])
                if bs[i] <= 0.48:
                    h2b.append(T[i])
                last = i
del K

print("H2: монет со спотом в дневном срезе — в среднем", f"{np.mean(list(daily_rank_pool.values())):.0f}")
print("H2 перп/спот ×2, ход ≤ ±3%:", per_month(np.array(h2a) * 3600 // 3600))
print("H2 то же + доля покупок перпа ≤ 48%:", per_month(h2b))
for thr in (0.10, 0.15):
    ms = pd.Series({k[1]: v for k, v in h3.items() if k[0] == thr}).sort_index()
    print(f"H3 пампы +{thr:.0%} из покоя (диапазон 24 ч ≤ 8%): в месяц медиана {ms.iloc[1:-1].median():.0f}")

# H6: события 🔑⁺ (только время и монета — доходы не читаются)
E = pd.read_pickle(os.path.join(D, "s142_2024–2026.pkl"))[["s", "T", "t"]]
fp_a = fp_b = fp_ab = n = 0
for s, Tun, tin in E.itertuples(index=False):
    if s not in HX or s not in F:
        continue
    T, x = HX[s]
    f = np.asarray(F[s])
    def fmean(t0, t1):
        m_ = (f[:, 0] >= t0) & (f[:, 0] < t1)
        if m_.sum() < 3:
            return np.nan
        return np.mean(f[m_, 2] / f[m_, 1] * 8)          # к 8 ч
    a1 = fmean(tin - 14 * 86400, tin); a0 = fmean(tin - 42 * 86400, tin - 14 * 86400)
    h = tin // 3600
    i1 = np.searchsorted(T, h); i0 = np.searchsorted(T, h - 24 * 14)
    if i1 >= len(T) or i0 <= 0 or not np.isfinite(a1) or not np.isfinite(a0):
        continue
    n += 1
    qv = x["qv"][i0:i1].sum(); tb = x["tb"][i0:i1].sum()
    A = (a1 - a0) <= -0.005 / 100 or a1 < 0
    B = qv > 0 and tb / qv <= 0.49
    fp_a += A; fp_b += B; fp_ab += A and B
months = (E["t"].max() - E["t"].min()) / 86400 / 30.4
print(f"H6: событий 🔑⁺ с данными {n} из {len(E)} ({len(E) / months:.1f} в месяц); фандинг упал или < 0 за 14 сут до входа: "
      f"{fp_a / n:.0%}; перп продают (покупки ≤ 49%): {fp_b / n:.0%}; оба: {fp_ab / n:.0%} → ~{fp_ab / months:.1f} в месяц")
