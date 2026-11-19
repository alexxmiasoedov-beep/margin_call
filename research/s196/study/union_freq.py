"""s196 — сводная частота класса «известная дата выхода на рынок» по всем источникам с историей без ключа (без доходов).
Событие — держатель (stash, делегатор, адрес) за сутки ≥ порога обращения CMC; ставки в месяц по периодам
10.2020–09.2022 / 10.2022–09.2024 / 10.2024–10.2026 складываются по источникам (монеты разные, совпадения
«монета-сутки» между источниками почти невозможны). Для выборочных источников (снимки Cosmos, недели EGLD/ROSE)
— частота по охвату выборки. «Срок» — за сколько суток до ликвидности известно событие."""
import collections
import glob
import json
from common196 import OUT, DAY, PERIODS, ts
from freq_lib import Circ, pname
import cosmos_freq as CF
import evm_freq as EF

P = [p for p, _, _ in PERIODS]
TH = (0.001, 0.005)


def cov(t0, t1):
    m = {}
    for n, a, b in PERIODS:
        lo, hi = max(t0, ts(a)), min(t1, ts(b))
        if hi > lo:
            m[n] = (hi - lo) / (30.4 * DAY)
    return m


TURN = {}
CIRC = {}
PX = {}


def _price(sym, t):
    """цена закрытия CMC на последнюю дату ≤ t (кэш по монете)."""
    import bisect
    if sym not in PX:
        rows = json.load(open(f"{OUT}/circ/{sym}.json"))
        rows = sorted((ts(d_), px) for d_, c_, px in rows if px)
        PX[sym] = ([a for a, _ in rows], [b for _, b in rows])
    xs, ys = PX[sym]
    i = bisect.bisect_right(xs, t) - 1
    return ys[i] if i >= 0 else None


def turn_ratio(sym, t, f):
    """стоимость события к среднему суточному обороту перпа за 7 сут до (панели s183); None — нет данных."""
    import size_turnover as ST
    key = (sym, int(t // DAY))
    if key not in TURN:
        if sym not in CIRC:
            CIRC[sym] = Circ(sym)
        c = CIRC[sym].at(t)
        px = _price(sym, t) if c else None
        tv = ST.turnover(sym, t)
        TURN[key] = (c * px / tv) if (c and px and tv) else None
    r = TURN[key]
    return None if r is None else f * r


TT = (0.1, 0.25)        # пороги в суточных оборотах перпа
TURN_RATES = {}


def rates_cont(E, t0, t1, sym=None, label=None):
    m = cov(t0, t1)
    out = {}
    for p in P:
        if p in m and m[p] > 0.5:
            out[p] = tuple(sum(1 for e in E if pname(e[0]) == p and e[1] >= th) / m[p] for th in TH)
    if sym and label:
        tr = {}
        for p in P:
            if p in m and m[p] > 0.5:
                big = [e for e in E if pname(e[0]) == p and e[1] >= 0.0005]
                rs = [turn_ratio(sym, e[0], e[1]) for e in big]
                tr[p] = tuple(sum(1 for r in rs if r is not None and r >= th) / m[p] for th in TT)
        TURN_RATES[label] = tr
    return out


def src_dot(net, sym):
    ev = json.load(open(f"{OUT}/{net}_unbonded.json"))
    c = Circ(sym)
    agg = collections.defaultdict(float)
    for b, tms, s, a in ev:
        if a:
            agg[(s, int(tms / 1000 // DAY))] += a
    E = [(d * DAY, v / c.at(d * DAY)) for (s, d), v in agg.items() if c.at(d * DAY)]
    return rates_cont(E, min(e[0] for e in E), max(e[0] for e in E), sym, f"{sym} анбондинг")


def src_cosmos():
    res = {}
    for ch, sym in CF.SYM.items():
        per = collections.defaultdict(lambda: [0.0, 0, 0, 0, 0])
        for p in sorted(glob.glob(f"{OUT}/cosmos/{ch}_*.json")):
            s = json.load(open(p))
            a = CF.analyze(s, sym, 6)
            if not a or not pname(a["t"]):
                continue
            g = per[pname(a["t"])]
            g[0] += a["ut_d"] / 30.4
            g[1] += sum(f >= TH[0] for f, *_ in a["e1"])
            g[2] += sum(f >= TH[1] for f, *_ in a["e1"])
            rs = [turn_ratio(sym, a["t"], f) for f, *_ in a["e1"] if f >= 0.0005]
            g[3] += sum(1 for r in rs if r is not None and r >= TT[0])
            g[4] += sum(1 for r in rs if r is not None and r >= TT[1])
        res[f"{sym} анбондинг (архив, снимки)"] = {p: (g[1] / g[0], g[2] / g[0]) for p, g in per.items()}
        TURN_RATES[f"{sym} анбондинг (архив)"] = {p: (g[3] / g[0], g[4] / g[0]) for p, g in per.items()}
    return res


def src_sampled(path, sym, amount_of, sender_ix=1):
    d = json.load(open(f"{OUT}/{path}"))
    c = Circ(sym)
    months = collections.Counter()
    E = []
    for k, rows in d.items():
        t = int(k)
        if pname(t):
            months[pname(t)] += 1 / 30.4
        agg = collections.defaultdict(float)
        for r in rows:
            a = amount_of(r)
            if a:
                agg[r[sender_ix]] += a
        if c.at(t):
            E += [(t, v / c.at(t)) for v in agg.values()]
    return {p: tuple(sum(1 for t, f in E if pname(t) == p and f >= th) / months[p] for th in TH) for p in months if months[p] > 0.5}


def src_simple_evm(name, sym, kind):
    circ = Circ(sym)
    agg = collections.defaultdict(float)
    for b, tx, tp, data in EF.load(name):
        t = EF.btime(b)
        w = EF.words(data)
        if kind == "api3":
            a, h = w[0] / 1e18, EF.addr(tp[1])
        elif kind in ("grt", "lpt"):
            a, h = w[1] / 1e18, EF.addr(tp[2])
        elif kind == "aave":
            if not w:
                continue
            a, h = w[0] / 1e18, EF.addr(tp[1])
        agg[(h, int(t // DAY))] += a
    E = [(d * DAY, v / circ.at(d * DAY)) for (h, d), v in agg.items() if circ.at(d * DAY)]
    return rates_cont(E, min(e[0] for e in E), max(e[0] for e in E), sym, f"{sym} {name}")


def src_ve(name, sym, start):
    import io
    import contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        H = EF.ve_calendar(name, sym, start)
    E = [(t, f) for t, f, *_ in H]
    return rates_cont(E, ts(start), max(e[0] for e in E), sym, f"{sym} {name}")


def src_tezos():
    import calendar, time
    d = json.load(open(f"{OUT}/tezos_unstake.json"))
    c = Circ("XTZ")
    agg = collections.defaultdict(float)
    for r in d["unstake"]:
        t = calendar.timegm(time.strptime(r["timestamp"][:19], "%Y-%m-%dT%H:%M:%S"))
        agg[(r.get("staker.address"), t // DAY)] += r["amount"] / 1e6
    E = [(k[1] * DAY, v / c.at(k[1] * DAY)) for k, v in agg.items() if c.at(k[1] * DAY)]
    return rates_cont(E, min(e[0] for e in E), max(e[0] for e in E), "XTZ", "XTZ unstake")


def src_aptos():
    import tezos_aptos_freq as TA
    import bisect, calendar, time
    d = json.load(open(f"{OUT}/aptos_unlock.json"))
    vt = sorted((int(v[0]), calendar.timegm(time.strptime(v[1][:19], "%Y-%m-%dT%H:%M:%S"))) for v in d["vt"].values())
    xs = [a for a, _ in vt]

    def vtime(v):
        i = max(0, min(bisect.bisect_right(xs, v) - 1, len(vt) - 2))
        (v0, t0), (v1, t1) = vt[i], vt[i + 1]
        return t0 + (t1 - t0) * (v - v0) / max(1, v1 - v0)
    c = Circ("APT")
    agg = collections.defaultdict(float)
    for v, amt, dl, pool in d["rows"]:
        agg[(dl, int(vtime(v) // DAY))] += amt
    E = [(k[1] * DAY, val / c.at(k[1] * DAY)) for k, val in agg.items() if c.at(k[1] * DAY)]
    return rates_cont(E, ts("2023-02-01"), max(e[0] for e in E), "APT", "APT unlock")


def src_avax():
    """выборка Glacier: самые новые и самые старые завершённые валидации; концы ставок ≥ порога, все (с перезапуском)."""
    p = f"{OUT}/avax_validators.json"
    try:
        d = json.load(open(p))
    except FileNotFoundError:
        return None
    c = Circ("AVAX")
    out = {}
    for key in ("completed_asc", "completed_desc"):
        rows = d.get(key) or []
        if not rows:
            continue
        E = [(t1, amt / c.at(t1)) for tx, node, amt, deleg, t0, t1, rew in rows if t1 and c.at(t1)]
        r = rates_cont(E, min(e[0] for e in E), max(e[0] for e in E))
        out.update(r)
    return out


SRC = [
    ("Cosmos SDK", "21 (TIA 14 с 2026)", src_cosmos),
    ("DOT анбондинг (Statescan)", "28 (≈2 с 07.2026)", lambda: {"DOT": src_dot("polkadot", "DOT")}),
    ("KSM анбондинг (Statescan)", "7", lambda: {"KSM": src_dot("kusama", "KSM")}),
    ("EGLD unDelegate (выборка)", "10", lambda: {"EGLD": src_sampled(
        "egld_undelegate.json", "EGLD",
        lambda r: r[3] if (r[2].startswith("erd1qqqqqqqqqqqqqqqpqqqqqqqqqqqqqqqqqqqqqqqqqqqqq") and r[3] and r[3] < 5e7) else None)}),
    ("ROSE ReclaimEscrow (выборка)", "14", lambda: {"ROSE": src_sampled(
        "rose_reclaim.json", "ROSE",
        (lambda ex: (lambda x: ex[x[4]][0] if x[4] in ex and ex[x[4]][0] else x[3]))(json.load(open(f"{OUT}/rose_exact.json"))))}),
    ("XTZ unstake (TzKT)", "≈5", lambda: {"XTZ": src_tezos()}),
    ("APT unlock (GraphQL, до 06.2025)", "≤14", lambda: {"APT": src_aptos()}),
    ("AVAX конец ставки (Glacier)", "14–365", lambda: {"AVAX": src_avax()}),
    ("stkAAVE Cooldown", "20", lambda: {"AAVE": src_simple_evm("stkaave", "AAVE", "aave")}),
    ("API3 ScheduledUnstake", "7", lambda: {"API3": src_simple_evm("api3", "API3", "api3")}),
    ("GRT L1 StakeDelegatedLocked", "≈26", lambda: {"GRT": src_simple_evm("grt_l1", "GRT", "grt")}),
    ("LPT L1 Unbond", "7", lambda: {"LPT": src_simple_evm("lpt_l1", "LPT", "lpt")}),
    ("veCRV конец блокировки", "≥7", lambda: {"CRV": src_ve("vecrv", "CRV", "2020-10-01")}),
    ("vePENDLE конец блокировки", "≥7", lambda: {"PENDLE": src_ve("vependle", "PENDLE", "2022-12-01")}),
    ("veFXS конец блокировки", "≥7", lambda: {"FXS": src_ve("vefxs", "FXS", "2021-03-01")}),
    ("veYFI конец блокировки", "≥7", lambda: {"YFI": src_ve("veyfi", "YFI", "2023-04-01")}),
]


DEFI = ("stkAAVE", "API3", "GRT", "LPT", "veCRV", "vePENDLE", "veFXS", "veYFI")


def main():
    tot = collections.defaultdict(lambda: [0.0, 0.0])
    grp = {"Г1 PoS": collections.defaultdict(lambda: [0.0, 0.0]), "Г2 DeFi": collections.defaultdict(lambda: [0.0, 0.0])}
    print(f"{'источник':42s} {'срок, сут':>18s} | " + " | ".join(f"{p:^17s}" for p in P))
    print(f"{'':42s} {'':>18s} | " + " | ".join(f"{'≥0,1%':>8s} {'≥0,5%':>8s}" for p in P))
    for name, lag, fn in SRC:
        try:
            res = fn()
        except Exception as e:
            print(f"{name:42s} ошибка {repr(e)[:80]}")
            continue
        for sub, r in res.items():
            if not r:
                print(f"{name:42s} {lag:>18s} | нет данных")
                continue
            cells = []
            for p in P:
                if p in r:
                    cells.append(f"{r[p][0]:8.1f} {r[p][1]:8.1f}")
                    tot[p][0] += r[p][0]
                    tot[p][1] += r[p][1]
                    g = grp["Г2 DeFi" if name.startswith(DEFI) else "Г1 PoS"]
                    if not name.startswith("AVAX"):
                        g[p][0] += r[p][0]
                        g[p][1] += r[p][1]
                else:
                    cells.append(f"{'—':>8s} {'—':>8s}")
            label = sub if name == "Cosmos SDK" else name
            print(f"{label:42s} {lag:>18s} | " + " | ".join(cells))
    print(f"{'ИТОГО (сумма источников с историей)':42s} {'':>18s} | " + " | ".join(f"{tot[p][0]:8.1f} {tot[p][1]:8.1f}" for p in P))
    for gname, g in grp.items():
        print(f"{'  в том числе ' + gname + (' (без AVAX)' if gname.startswith('Г1') else ''):42s} {'':>18s} | "
              + " | ".join(f"{g[p][0]:8.1f} {g[p][1]:8.1f}" for p in P))
    print("\nТо же по размеру к обороту: событие ≥ 0,1 / ≥ 0,25 суточного оборота перпа Binance за 7 сут до (в месяц;"
          " только источники с непрерывной историей)")
    tt = collections.defaultdict(lambda: [0.0, 0.0])
    for lab, r in TURN_RATES.items():
        cells = []
        for p in P:
            if p in r:
                cells.append(f"{r[p][0]:8.1f} {r[p][1]:8.1f}")
                tt[p][0] += r[p][0]
                tt[p][1] += r[p][1]
            else:
                cells.append(f"{'—':>8s} {'—':>8s}")
        print(f"{lab:42s} {'':>18s} | " + " | ".join(cells))
    print(f"{'ИТОГО':42s} {'':>18s} | " + " | ".join(f"{tt[p][0]:8.1f} {tt[p][1]:8.1f}" for p in P))


if __name__ == "__main__":
    main()
