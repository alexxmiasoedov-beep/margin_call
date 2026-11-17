"""s125 — шаги 1 и 2 протокола (после o9grid.py в ~/mc_data и ~/mc_oos)."""
import itertools
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s43"))
from oi_test import ct  # noqa: E402

NEW = pd.read_pickle("/home/user/mc_data/s125_2024.pkl"); OLD = pd.read_pickle("/home/user/mc_oos/s125_2022.pkl")
mn = lambda X: (X.t.max() - X.t.min()) / (30.4 * 86400)
base = lambda x: (x.r1 >= 0.05) & (x.share >= 0.20)
print("Шаг 1 — 2024–2026 гг., только новые сделки (не входят в нынешний ⏰):")
best = None
for r, sh in itertools.product((0.03, 0.04, 0.05), (0.10, 0.20, 0.30)):
    x = NEW[(NEW.r1 >= r) & (NEW.share >= sh) & ~base(NEW)]
    if len(x) < 8:
        print(f"  r1 ≥ {r:.0%}, доля ≥ {sh:.0%}: новых {len(x)}"); continue
    m, t, n = ct(x.net, x.t); dp, tp, _ = ct(x.net - x.pl, x.t)
    ok = t >= 3 and tp >= 2
    print(f"  r1 ≥ {r:.0%}, доля ≥ {sh:.0%}: новых {n} ({n / mn(NEW):.1f}/мес) {m:+.2%} (t {t:+.1f}), сверх плацебо {dp:+.2%} (t {tp:+.1f})"
          f"{'  ← годится' if ok else ''}")
    if ok and (best is None or n > best[2]):
        best = (r, sh, n)
if best is None:
    print("ни один вариант не прошёл шаг 1"); sys.exit()
r, sh, _ = best
print(f"\nВыбран: r1 ≥ {r:.0%}, доля ≥ {sh:.0%}")
for lab, X in (("2022–2024 (проверка)", OLD), ("2024–2026 (подбор)", NEW)):
    x = X[(X.r1 >= r) & (X.share >= sh) & ~base(X)]
    m, t, n = ct(x.net, x.t); dp, tp, _ = ct(x.net - x.pl, x.t)
    y = X[base(X)]; mb, tb, nb = ct(y.net, y.t)
    print(f"  {lab}: новые сделки n={n} ({n / mn(X):.1f}/мес) {m:+.2%} (t {t:+.1f}), сверх плацебо {dp:+.2%} (t {tp:+.1f}) | "
          f"нынешний ⏰ n={nb} {mb:+.2%} (t {tb:+.1f})")
