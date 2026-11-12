"""Анатомия сильного хода (поиск — первая половина; --confirm — вторая): после роста ≥ +25% к рынку за 24 ч (или обвала
≤ −20%) — какие признаки хода предсказывают откат или продолжение. Событие — первый 4-часовой срез, где условие выполнено,
не чаще раза в 3 суток на монету. По каждому признаку — терцили среди событий: средний доход к рынку (лонг) через 1 и 3
суток, t по дням. Таблица — s23/long4h.pkl (g6_precursors.py). Запуск из папки с данными."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from feat23 import CUT
from common23 import ct

CONF = "--confirm" in sys.argv
L = pd.read_pickle("s23/long4h.pkl")
L = L[(L["T"] >= CUT) if CONF else (L["T"] < CUT)]


def events(cond):
    E = L[cond(L)].sort_values("T")
    keep, last = [], {}
    for i, (s, T) in enumerate(zip(E.s.values, E["T"].values)):
        if T - last.get(s, -1e18) >= 3 * 86400:
            keep.append(i)
        last[s] = T if T - last.get(s, -1e18) >= 3 * 86400 else last[s]
    return E.iloc[keep]


feats = ["R", "R72", "R7d", "PHI", "D", "B", "A", "TS", "VC", "PMW", "dPM", "F8", "ETA3", "DH30", "DL30", "NPUMP", "AGE", "Vb", "lam"]
for nm, cond in (("РОСТ ≥ +25% за 24 ч", lambda d: np.exp(d.R) - 1 >= 0.25), ("ОБВАЛ ≤ −20% за 24 ч", lambda d: np.exp(d.R) - 1 <= -0.20)):
    E = events(cond)
    print(f"\n===== {nm} ({'вторая' if CONF else 'первая'} половина): событий {len(E)}, монет {E.s.nunique()}")
    for h in ("Y24", "Y72"):
        m, t, n = ct(E[h], E["T"])
        print(f"  все события: {h} {m * 100:+.2f}% (t {t:+.1f}, n {n}), в плюсе {(E[h] > 0).mean():.0%}")
    for f in feats:
        x = E[f]
        ok = x.notna() & E.Y72.notna()
        if ok.sum() < 60:
            continue
        q = pd.qcut(x[ok].rank(method="first"), 3, labels=False)
        line = []
        for k in range(3):
            sel = E[ok][q == k]
            m1, t1, _ = ct(sel.Y24, sel["T"]); m3, t3, _ = ct(sel.Y72, sel["T"])
            line.append(f"{k + 1}: {m1 * 100:+5.1f}/{m3 * 100:+5.1f}% (t {t3:+.1f})")
        lo, hi = E[ok][q == 0], E[ok][q == 2]
        d3 = hi.Y72.mean() - lo.Y72.mean()
        # t разницы крайних терцилей (по дням не кластеризуем — грубо, через независимость)
        se = np.sqrt(hi.Y72.var() / len(hi) + lo.Y72.var() / len(lo))
        print(f"  {f:>6} [{x[ok].quantile(1 / 3):+.3g} | {x[ok].quantile(2 / 3):+.3g}]  " + "  ".join(line)
              + f"   3−1: {d3 * 100:+.1f} п. п. (≈t {d3 / se:+.1f})")
