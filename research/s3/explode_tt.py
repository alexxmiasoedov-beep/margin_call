"""Пробуждение спящей монеты: подбор порогов только на 1-м году, проверка на 2-м (шорт 10/15/24 ч)."""
import pickle, datetime, itertools
import numpy as np, pandas as pd
exec(open("s2/explode.py").read().split('if __name__ == "__main__":')[0])
CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp()
G = []
for X, lo, hi in itertools.product((10, 20, 30, 50, 80), (0.05, 0.1, 0.15), (0.3, 0.5, 1.0)):
    ev = events(X, lo, hi)
    if len(ev) < 100: continue
    d = table(ev, 0.1, 0.15, 96); a1, a2 = d[d.t < CUT].p, d[d.t >= CUT].p
    if len(a1) >= 60: G.append((X, lo, hi, len(a1), a1.mean() * 100, len(a2), a2.mean() * 100))
G = pd.DataFrame(G, columns=["объём ×", "рост от", "рост до", "n1", "1-й год %", "n2", "2-й год %"]).sort_values("1-й год %", ascending=False)
pd.set_option("display.width", 200); print(G.head(12).round(2).to_string(index=False))
print(f"\nвсего вариантов {len(G)}; 2-й год в плюсе у {(G['2-й год %'] > 0).sum()}; средний 2-й год {G['2-й год %'].mean():+.2f}%; корреляция рангов {G['1-й год %'].rank().corr(G['2-й год %'].rank()):.2f}")
