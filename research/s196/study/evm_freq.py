"""s196 — расписанные выходы в Ethereum (логи evm_ve.py), без доходов.
- ve-блокировки (veCRV, veFXS, veSTG: Deposit/Withdraw; vePENDLE: NewLockPosition/Withdraw; veYFI: ModifyLock):
  состояние держателя (сумма, конец) восстанавливается по событиям; конец блокировки — неделя (четверг 00:00 UTC).
  Календарь «за 7 сут»: на W − 7 сут видно, у кого блокировка кончается в W. События: H — держатель с суммой ≥ порога,
  W — вся неделя W ≥ порога; плюс доля, реально выведенная (Withdraw) в 14 сут после W (поведение, не цена).
- API3 ScheduledUnstake (вывод через 7 сут, время в событии); GRT L1 StakeDelegatedLocked (28 эпох ≈ 26 сут);
  LPT L1 Unbond (7 раундов); stkAAVE Cooldown (20 сут, сумма только в новой версии события).
Время блоков — интерполяция по кэшу s160 (cache_blocktime.json)."""
import bisect
import collections
import gzip
import json
import time
from common196 import OUT, DAY, PERIODS, ts, D
from freq_lib import Circ, pname, fmt_t, summarize

BT = json.load(open(f"{D}/s160/cache_blocktime.json"))
BX = sorted((int(k), v) for k, v in BT.items())
BK = [a for a, _ in BX]


def btime(b):
    i = bisect.bisect_right(BK, b) - 1
    i = max(0, min(i, len(BX) - 2))
    (b0, t0), (b1, t1) = BX[i], BX[i + 1]
    return t0 + (t1 - t0) * (b - b0) / max(1, b1 - b0)


def words(data):
    h = data[2:]
    return [int(h[i:i + 64], 16) for i in range(0, len(h), 64)]


def addr(topic):
    return "0x" + topic[-40:]


def load(name):
    return json.load(gzip.open(f"{OUT}/evm/{name}.json.gz", "rt"))


TOP = {
    "Deposit": "0x4566dfc29f6f11d13a418c26a02bef7c28bae749d4de47e4e6a7cddea6730d59",
    "Withdraw": "0xf279e6a1f5e320cca91135676d9cb6e44ca8a08c0b88342bcdb1144f6511b568",
    "NewLockPosition": "0xb1a3371956c54dc1d83695b4a006b051c8313ee986e533b6b964e77c9066fc2c",
}


def ve_events(name):
    """→ [(t, kind, holder, amount, end)] по времени; kind: set|add|wd."""
    out = []
    for b, tx, tp, data in load(name):
        t = btime(b)
        w = words(data)
        if name == "vependle":
            if tp[0] == TOP["NewLockPosition"]:
                out.append((t, "set", addr(tp[1]), w[0] / 1e18, w[1]))
            else:
                out.append((t, "wd", addr(tp[1]), w[0] / 1e18 if w else 0, 0))
        elif name == "veyfi":
            out.append((t, "set", addr(tp[2]), w[0] / 1e18, w[1]))
        else:
            if tp[0] == TOP["Deposit"]:
                out.append((t, "add", addr(tp[1]), w[0] / 1e18, int(tp[2], 16)))
            elif tp[0] == TOP["Withdraw"]:
                out.append((t, "wd", addr(tp[1]), w[0] / 1e18, 0))
    out.sort(key=lambda x: x[0])
    return out


def ve_calendar(name, sym, start):
    """календарь концов блокировок «за 7 сут»; держатели-«перекладчики» (≥ 2 прошлых перезамков в 14 сут после конца)
    исключаются — это видно в реальном времени по их истории."""
    ev = ve_events(name)
    circ = Circ(sym)
    st = {}                       # держатель → [сумма, конец]
    relock = collections.Counter()
    last_wd = {}                  # держатель → (время вывода, конец до вывода)
    i = 0
    W = int(ts(start) // (7 * DAY) * (7 * DAY))
    tend = time.time() - 7 * DAY
    H, Wk, rows = [], [], []
    while W < tend:
        check = W - 7 * DAY
        while i < len(ev) and ev[i][0] < check:
            t, k, h, a, e = ev[i]
            prev = st.get(h, [0.0, 0])
            if k in ("add", "set"):
                # перезамок: прежний конец уже прошёл (или проходит) — или вывод был ≤ 14 сут назад
                if (prev[0] > 0 and prev[1] and prev[1] <= t + DAY) or (h in last_wd and t - last_wd[h] <= 14 * DAY):
                    relock[h] += 1
                if k == "add":
                    s_ = st.setdefault(h, [0.0, 0])
                    s_[0] += a
                    s_[1] = max(s_[1], e)
                else:
                    st[h] = [a, e]
            else:
                last_wd[h] = t
                st[h] = [0.0, 0]
            i += 1
        c = circ.at(check)
        exp = [(h, s_[0]) for h, s_ in st.items() if s_[1] and abs(s_[1] - W) < DAY and s_[0] > 0 and relock[h] < 2]
        tot = sum(a for _, a in exp)
        if c:
            Wk.append((check, tot / c))
            for h, a in exp:
                H.append((check, a / c, h, W))
        rows.append((W, tot, c))
        W += 7 * DAY
    # поведение (задним числом, только описание): вывел в [W−1; W+14] и не перезамкнул до W+14
    wd_t = collections.defaultdict(list)
    lk_t = collections.defaultdict(list)
    for t, k, h, a, e in ev:
        (wd_t if k == "wd" else lk_t)[h].append(t)
    big = [x for x in H if x[1] >= 0.001]
    took = sum(1 for chk, f, h, W in big if any(W - DAY <= t <= W + 14 * DAY for t in wd_t.get(h, []))
               and not any(W - DAY <= t <= W + 14 * DAY for t in lk_t.get(h, [])))
    months = collections.Counter(pname(r[0] - 7 * DAY) for r in rows if pname(r[0] - 7 * DAY))
    months = {k: v * 7 / 30.4 for k, v in months.items()}
    print(f"\n{name} ({sym}): событий {len(ev)}, держателей {len(st)}, недель {len(rows)}, "
          f"исключено «перекладчиков» {sum(1 for v in relock.values() if v >= 2)}")
    summarize([(t, f) for t, f, *_ in H], months, f"{sym} держатель (конец в W, видно за 7 сут)")
    summarize(Wk, months, f"{sym} неделя целиком")
    if big:
        print(f"  держатели ≥0,1%: вывели в [W−1; W+14] и не перезамкнули — {took} из {len(big)} ({100 * took / len(big):.0f}%)")
    tops = sorted(H, key=lambda x: -x[1])[:6]
    print("  крупнейшие:", "; ".join(f"{fmt_t(W)} {100 * f:.2f}% ({h[:10]}…)" for _, f, h, W in tops))
    med = sorted(f for _, f in Wk)
    if med:
        print(f"  неделя: медиана {100 * med[len(med) // 2]:.3f}% обращения, p90 {100 * med[9 * len(med) // 10]:.3f}%")
    return H


def simple(name, sym, kind):
    circ = Circ(sym)
    ev = []
    t_first = None
    for b, tx, tp, data in load(name):
        t = btime(b)
        t_first = t if t_first is None else min(t_first, t)
        w = words(data)
        if kind == "api3":
            amt, when, holder = w[0] / 1e18, w[2], addr(tp[1])
        elif kind == "grt":
            amt, when, holder = w[1] / 1e18, None, addr(tp[2])
        elif kind == "lpt":
            amt, when, holder = w[1] / 1e18, None, addr(tp[2])
        elif kind == "aave":
            if len(tp) == 2 and not w:
                ev.append((t, None, addr(tp[1])))
                continue
            amt, when, holder = (w[0] / 1e18 if w else None), None, addr(tp[1])
        ev.append((t, amt, holder))
    agg = collections.defaultdict(float)
    n_none = 0
    for t, a, h in ev:
        if a is None:
            n_none += 1
            continue
        agg[(h, int(t // DAY))] += a
    E = [(d * DAY, v / circ.at(d * DAY), h) for (h, d), v in agg.items() if circ.at(d * DAY)]
    if not E:
        print(f"\n{name}: событий {len(ev)} (без суммы {n_none})")
        return
    t0, t1 = min(e[0] for e in E), max(e[0] for e in E)
    m = {}
    for n, a, b in PERIODS:
        lo, hi = max(t0, ts(a)), min(t1, ts(b))
        if hi > lo:
            m[n] = (hi - lo) / (30.4 * DAY)
    print(f"\n{name} ({sym}): событий {len(ev)} (без суммы {n_none}), {fmt_t(t0)} … {fmt_t(t1)}")
    summarize([(t, f) for t, f, _ in E], m, f"{sym} держатель-сутки")
    print("  крупнейшие:", "; ".join(f"{fmt_t(t)} {100 * f:.2f}%" for t, f, _ in sorted(E, key=lambda x: -x[1])[:6]))


if __name__ == "__main__":
    ve_calendar("vecrv", "CRV", "2020-10-01")
    ve_calendar("vependle", "PENDLE", "2022-12-01")
    ve_calendar("vefxs", "FXS", "2021-03-01")
    ve_calendar("veyfi", "YFI", "2023-04-01")
    simple("api3", "API3", "api3")
    simple("grt_l1", "GRT", "grt")
    simple("lpt_l1", "LPT", "lpt")
    simple("stkaave", "AAVE", "aave")
