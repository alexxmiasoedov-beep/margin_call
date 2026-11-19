"""s196 — частоты выходов из стейкинга Tezos (unstake, с 02.2024) и Aptos (UnlockStakeEvent пулов делегирования,
с 2023 г.) — без доходов. Событие — участник за сутки ≥ порога обращения CMC."""
import bisect
import calendar
import collections
import json
import time
from common196 import OUT, DAY, PERIODS, ts
from freq_lib import Circ, pname, fmt_t, summarize


def months_cov(t0, t1):
    m = collections.Counter()
    for n, a, b in PERIODS:
        lo, hi = max(t0, ts(a)), min(t1, ts(b))
        if hi > lo:
            m[n] = (hi - lo) / (30.4 * DAY)
    return dict(m)


def tparse(s):
    return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))


def tezos():
    d = json.load(open(f"{OUT}/tezos_unstake.json"))
    c = Circ("XTZ")
    agg = collections.defaultdict(float)
    for r in d["unstake"]:
        t = tparse(r["timestamp"])
        agg[(r["staker.address"] if "staker.address" in r else r["staker"]["address"], t // DAY)] += r["amount"] / 1e6
    ev = [(k[1] * DAY, v / c.at(k[1] * DAY), k[0]) for k, v in agg.items() if c.at(k[1] * DAY)]
    t0 = min(e[0] for e in ev); t1 = time.time()
    print(f"Tezos: unstake {len(d['unstake'])}, finalize {len(d['finalize'])}, с {fmt_t(t0)}")
    # задержка unstake → finalize (сут) по участникам
    fin = collections.defaultdict(list)
    for r in d["finalize"]:
        fin[r["staker.address"] if "staker.address" in r else r["staker"]["address"]].append(tparse(r["timestamp"]))
    lags = []
    for r in d["unstake"]:
        s = r["staker.address"] if "staker.address" in r else r["staker"]["address"]
        t = tparse(r["timestamp"])
        later = [f for f in fin.get(s, []) if f > t]
        if later:
            lags.append((min(later) - t) / DAY)
    lags.sort()
    if lags:
        print(f"  задержка unstake → первый finalize: медиана {lags[len(lags) // 2]:.1f} сут, p10 {lags[len(lags) // 10]:.1f}, "
              f"p90 {lags[9 * len(lags) // 10]:.1f}")
    summarize([(t, f) for t, f, _ in ev], months_cov(t0, t1), "XTZ участник-сутки")
    print("  крупнейшие:", "; ".join(f"{fmt_t(t)} {100 * f:.2f}%" for t, f, _ in sorted(ev, key=lambda x: -x[1])[:6]))


def aptos():
    d = json.load(open(f"{OUT}/aptos_unlock.json"))
    vt = sorted((int(v[0]), tparse(v[1])) for v in d["vt"].values())
    xs = [a for a, _ in vt]

    def vtime(v):
        i = bisect.bisect_right(xs, v) - 1
        i = max(0, min(i, len(vt) - 2))
        (v0, t0), (v1, t1) = vt[i], vt[i + 1]
        return t0 + (t1 - t0) * (v - v0) / max(1, v1 - v0)
    c = Circ("APT")
    agg = collections.defaultdict(float)
    seen = set()
    for v, amt, dl, pool in d["rows"]:
        if (v, dl, pool, round(amt, 8)) in seen:      # одно действие бывает и v1-, и v2-событием
            continue
        seen.add((v, dl, pool, round(amt, 8)))
        t = vtime(v)
        agg[(dl, int(t // DAY))] += amt
    ev = [(k[1] * DAY, v / c.at(k[1] * DAY), k[0]) for k, v in agg.items() if c.at(k[1] * DAY)]
    tmax = max(e[0] for e in ev)
    print(f"\nAptos: UnlockStake(Event) ≥ 10 тыс. APT (v1 и v2, без повторов): {len(seen)}, первое {fmt_t(min(e[0] for e in ev))}, "
          f"последнее {fmt_t(tmax)}")
    summarize([(t, f) for t, f, _ in ev], months_cov(vtime(0) if False else 1675209600, tmax), "APT делегатор-сутки")
    print("  крупнейшие:", "; ".join(f"{fmt_t(t)} {100 * f:.2f}% ({s[:10]}…)" for t, f, s in sorted(ev, key=lambda x: -x[1])[:8]))


if __name__ == "__main__":
    tezos()
    aptos()
