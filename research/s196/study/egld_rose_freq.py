"""s196 — частоты выходов EGLD (unDelegate, 10 сут) и ROSE (ReclaimEscrow, ≈14 сут) по выборке «первые 7 суток месяца»
(без доходов). Событие — отправитель за сутки ≥ порога обращения CMC; в месяц = число × 30,4/7 по периодам.
EGLD: только системные контракты делегирования (erd1qqqqqqqqqqqqqqqpqqqq…), у прочих контрактов «unDelegate» —
другие аргументы. ROSE: доли × курс доли ≥ 1 → для долей ≥ 1,67 млн точная сумма из события debonding_start."""
import collections
import json
import time
from common196 import OUT, DAY, PERIODS
from freq_lib import Circ, pname, fmt_t, THR, summarize

SYS = "erd1qqqqqqqqqqqqqqqpqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"


def calc(days, rows_by_day, circ, label, amount_of):
    ev, months = [], collections.Counter()
    for k, rows in days.items():
        t = int(k)
        pn = pname(t)
        if pn:
            months[pn] += 1 / 30.4   # сутки выборки -> месяцы охвата
        agg = collections.defaultdict(float)
        for r in rows:
            a = amount_of(r)
            if a:
                agg[r[1]] += a
        c = circ.at(t)
        if not c:
            continue
        for s, a in agg.items():
            ev.append((t, a / c, s))
    summarize([(t, f) for t, f, _ in ev], dict(months), label)
    big = sorted(ev, key=lambda x: -x[1])[:8]
    print("  крупнейшие:", "; ".join(f"{fmt_t(t)} {100 * f:.2f}% ({s[:12]}…)" for t, f, s in big))
    return ev


def main():
    e = json.load(open(f"{OUT}/egld_undelegate.json"))
    print("EGLD: unDelegate, суток в выборке", len(e), "(с 01.2021)")
    calc(e, None, Circ("EGLD"), "EGLD отправитель-сутки",
         lambda r: r[3] if (r[2].startswith(SYS) and r[3] is not None and r[3] < 5e7) else None)
    r = json.load(open(f"{OUT}/rose_reclaim.json"))
    ex = json.load(open(f"{OUT}/rose_exact.json"))
    print("\nROSE: ReclaimEscrow, суток в выборке", len(r), "(с 05.2022); точных сумм", len(ex))
    ratio = [v[0] / x[3] for rows in r.values() for x in rows if x[4] in ex and x[3] > 0 and ex[x[4]][0] > 0
             for v in [ex[x[4]]]]
    if ratio:
        ratio.sort()
        print(f"  курс доли (сумма/доли) по точным: медиана {ratio[len(ratio) // 2]:.3f}, мин {ratio[0]:.3f}, макс {ratio[-1]:.3f}")
    calc(r, None, Circ("ROSE"), "ROSE отправитель-сутки",
         lambda x: (ex[x[4]][0] if x[4] in ex and ex[x[4]][0] else x[3]))


if __name__ == "__main__":
    main()
