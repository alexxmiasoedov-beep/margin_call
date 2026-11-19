"""s196 — частоты анбондинга Polkadot (28 сут до 2026 г.) и Kusama (7 сут) по событиям Staking.Unbonded (Statescan),
без доходов. Событие — stash за сутки ≥ порога обращения CMC (пулы номинирования — один stash пула на действие участника).
Покрытие: Polkadot 05.2020 – 04.11.2025, Kusama — до 07.10.2025 (дальше стейкинг на Asset Hub; с 07.2026 у Polkadot
анбондинг номинаторов ≈ 2 сут — референдум 1910)."""
import collections
import json
import sys
from common196 import OUT, DAY, PERIODS, ts
from freq_lib import Circ, pname, fmt_t, summarize


def run(net, sym):
    ev = json.load(open(f"{OUT}/{net}_unbonded.json"))
    c = Circ(sym)
    agg = collections.defaultdict(float)
    for b, tms, stash, amt in ev:
        if amt:
            agg[(stash, int(tms / 1000 // DAY))] += amt
    E = [(d * DAY, v / c.at(d * DAY), s) for (s, d), v in agg.items() if c.at(d * DAY)]
    t0, t1 = min(e[0] for e in E), max(e[0] for e in E)
    m = {}
    for n, a, b in PERIODS:
        lo, hi = max(t0, ts(a)), min(t1, ts(b))
        if hi > lo:
            m[n] = (hi - lo) / (30.4 * DAY)
    print(f"\n{net} ({sym}): событий Unbonded {len(ev)}, stash-суток {len(agg)}, {fmt_t(t0)} … {fmt_t(t1)}")
    summarize([(t, f) for t, f, _ in E], m, f"{sym} stash-сутки")
    dayagg = collections.defaultdict(float)
    for t, f, s in E:
        dayagg[t] += f
    summarize(list(dayagg.items()), m, f"{sym} сутки сети целиком")
    top = sorted(E, key=lambda x: -x[1])[:8]
    print("  крупнейшие:", "; ".join(f"{fmt_t(t)} {100 * f:.2f}% ({s[:8]}…)" for t, f, s in top))
    vals = sorted(dayagg.values())
    print(f"  сутки сети: медиана {100 * vals[len(vals) // 2]:.3f}% обращения, p90 {100 * vals[9 * len(vals) // 10]:.3f}%")
    # повторяющиеся stash среди крупных (≥0,1%)
    rep = collections.Counter(s for t, f, s in E if f >= 0.001)
    print("  stash с ≥0,1% чаще всего:", [(s[:8], n) for s, n in rep.most_common(5)])


if __name__ == "__main__":
    for net, sym in (("polkadot", "DOT"), ("kusama", "KSM")):
        try:
            run(net, sym)
        except FileNotFoundError:
            print(net, "нет файла")
