"""s196 — AVAX: концы ставок валидаторов по выборке Glacier (100 страниц самых новых и 100 самых старых завершённых
валидаций), без доходов. Событие — конец ставки ≥ порога обращения CMC; «перекладчик» — тот же узел начал новую
валидацию в ±2 сут от конца (задним числом, только описание); доля перекладчиков среди прошлых концов узла видна
в реальном времени."""
import collections
import json
import time
from common196 import OUT, DAY
from freq_lib import Circ, pname, fmt_t

d = json.load(open(f"{OUT}/avax_validators.json"))
c = Circ("AVAX")
for key in ("completed_asc", "completed_desc"):
    rows = d.get(key) or []
    if not rows:
        continue
    starts = collections.defaultdict(list)
    for tx, node, amt, deleg, t0, t1, rew in rows:
        starts[node].append(t0)
    ends = [r for r in rows if r[5]]
    t_lo, t_hi = min(r[5] for r in ends), max(r[5] for r in ends)
    months = (t_hi - t_lo) / (30.4 * DAY)
    print(f"{key}: валидаций {len(rows)}, концы {fmt_t(t_lo)} … {fmt_t(t_hi)} ({months:.1f} мес)")
    dur = sorted((r[5] - r[4]) / DAY for r in ends)
    print(f"  срок ставки: медиана {dur[len(dur) // 2]:.0f} сут, p10 {dur[len(dur) // 10]:.0f}, p90 {dur[9 * len(dur) // 10]:.0f}")
    for th in (0.0005, 0.001, 0.005):
        big = [r for r in ends if c.at(r[5]) and r[2] >= th * c.at(r[5])]
        roll = [r for r in big if any(abs(s - r[5]) <= 2 * DAY for s in starts[r[1]] if s != r[4])]
        print(f"  конец ставки ≥ {100 * th:.2f}%: {len(big)} ({len(big) / months:.1f} в мес), из них узел сразу снова "
              f"в валидации {len(roll)} ({100 * len(roll) / max(1, len(big)):.0f}%) → без перезапуска {(len(big) - len(roll)) / months:.1f} в мес")
