"""s196 — ICP: календарь «нейрон станет ликвидным» по снимку 4000 крупнейших нейронов (ic-api, без ключа), без доходов.
Нейрон в состоянии Dissolving станет ликвидным через dissolve_delay_seconds; Dissolved — уже можно вывести."""
import collections
import json
import time
from common196 import OUT, DAY
from freq_lib import Circ, fmt_t

rows = json.load(open(f"{OUT}/icp_neurons.json"))
c = Circ("ICP").at(time.time() - DAY)
st = collections.Counter(r[2] for r in rows)
print("ICP: нейронов в снимке", len(rows), "состояния", dict(st), f"обращение {c:,.0f}")
dis = [(r[5] + r[3], r[1]) for r in rows if r[2] == "Dissolving"]
done = sum(r[1] for r in rows if r[2] == "Dissolved")
print(f"  Dissolved (можно вывести сейчас): {done:,.0f} ICP ({100 * done / c:.2f}% обращения)")
now = time.time()
for thr in (0.0005, 0.001, 0.005):
    big = [(t, a) for t, a in dis if a >= thr * c]
    n12 = [x for x in big if x[0] - now <= 365 * DAY]
    n3 = [x for x in big if x[0] - now <= 91 * DAY]
    print(f"  ≥ {100 * thr:.2f}%: растворяющихся {len(big)}; станут ликвидными за 3 мес — {len(n3)} "
          f"({len(n3) / 3:.1f} в мес), за 12 мес — {len(n12)} ({len(n12) / 12:.1f} в мес)")
by_m = collections.defaultdict(float)
for t, a in dis:
    if t - now <= 365 * DAY:
        by_m[time.strftime("%Y-%m", time.gmtime(t))] += a
print("  по месяцам (12 мес, все растворяющиеся из снимка, % обращения):",
      ", ".join(f"{m} {100 * v / c:.2f}%" for m, v in sorted(by_m.items())))
