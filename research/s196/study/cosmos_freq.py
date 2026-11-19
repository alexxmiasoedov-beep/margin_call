"""s196 — частоты выходов из анбондинга Cosmos SDK (без доходов): архивные снимки ATOM, TIA, KAVA по периодам и снимок
«сейчас» всех сетей с перпом. Событие E1 — делегатор (все валидаторы вместе) с завершением в одни сутки ≥ порога
обращения CMC на дату снимка; E2 — сутки завершения по сети целиком ≥ порога. Снимок охватывает анбондинги, начатые за
unbonding_time до него, поэтому частота в месяц = число × 30,4 / unbonding_time (сут). Итог — лог и
/home/user/mc_data/s196/cosmos_events.json."""
import collections
import calendar
import glob
import json
import os
import time
from common196 import OUT, DAY, PERIODS
from freq_lib import Circ, pname, fmt_t, THR

SYM = {"atom": "ATOM", "tia": "TIA", "kava": "KAVA"}
EXP = {"injective": 18, "dydx": 18, "dymension": 18, "fetchhub": 18, "zetachain": 18}


def tparse(s):
    return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))


def analyze(snap, sym, exp):
    t0 = snap.get("time") or 0
    if isinstance(t0, str):
        t0 = tparse(t0)
    rows = snap["rows"]
    if not rows:
        return None
    comp = [tparse(r[3]) for r in rows]
    ut = max(c - t0 for c in comp)  # ≈ unbonding_time
    ut_d = max(1.0, round(ut / DAY))
    circ = Circ(sym).at(t0)
    if not circ:
        return None
    by_del = collections.defaultdict(float)
    by_day = collections.defaultdict(float)
    for r, c in zip(rows, comp):
        amt = r[4] / 10 ** exp           # initial_balance
        by_del[(r[0], c // DAY)] += amt
        by_day[c // DAY] += amt
    tot = sum(by_day.values())
    e1 = sorted(((v / circ, d, k) for (k, d), v in by_del.items()), reverse=True)
    e2 = sorted(((v / circ, d) for d, v in by_day.items()), reverse=True)
    return dict(t=t0, ut_d=ut_d, circ=circ, queue=tot / circ, e1=e1, e2=e2, n=len(rows))


def main():
    out = {}
    print("== Архивные снимки (ATOM с 02.2022, TIA с 12.2023, KAVA с 07.2022)")
    for ch, sym in SYM.items():
        print(f"\n{sym}: дата | анбондинг, сут | очередь, % обращения | E1 делегаторов ≥0,1% / ≥0,5% | E2 суток ≥0,1% / ≥0,5% | крупнейший")
        per = collections.defaultdict(lambda: [0, 0.0, 0, 0, 0, 0])
        for p in sorted(glob.glob(f"{OUT}/cosmos/{ch}_*.json")):
            s = json.load(open(p))
            a = analyze(s, sym, 6)
            if not a:
                continue
            k1 = sum(f >= 0.001 for f, *_ in a["e1"]); k5 = sum(f >= 0.005 for f, *_ in a["e1"])
            d1 = sum(f >= 0.001 for f, _ in a["e2"]); d5 = sum(f >= 0.005 for f, _ in a["e2"])
            top = a["e1"][0]
            print(f"  {s['date']} | {a['ut_d']:.0f} | {100 * a['queue']:.2f}% | {k1} / {k5} | {d1} / {d5} | "
                  f"{100 * top[0]:.2f}% ({top[2][:14]}…, завершение {fmt_t(top[1] * DAY)})")
            pn = pname(a["t"])
            g = per[pn]
            g[0] += 1; g[1] += a["ut_d"]; g[2] += k1; g[3] += k5; g[4] += d1; g[5] += d5
            out.setdefault(sym, []).append(dict(date=s["date"], ut_d=a["ut_d"], queue=a["queue"],
                                                e1=[(f, d) for f, d, _ in a["e1"] if f >= 0.0005],
                                                e2=[(f, d) for f, d in a["e2"] if f >= 0.0005]))
        for pn, g in per.items():
            m = g[1] / 30.4
            print(f"  {pn}: снимков {g[0]}, охват {g[1]:.0f} сут → E1 ≥0,1%: {g[2] / m:.1f} в мес, ≥0,5%: {g[3] / m:.1f}; "
                  f"E2 ≥0,1%: {g[4] / m:.1f}, ≥0,5%: {g[5] / m:.1f}")
    print("\n== Снимок «сейчас» (11.2026), все сети с перпом: событий в месяц")
    print("сеть | анбондинг, сут | очередь, % обр. | E1 ≥0,05% | E1 ≥0,1% | E1 ≥0,5% | E2 ≥0,1% | E2 ≥0,5% | крупнейший E1")
    tot = collections.Counter()
    for p in sorted(glob.glob(f"{OUT}/cosmos/now_*.json")):
        s = json.load(open(p))
        sym = s["tk"]
        if sym in ("INIT", "OM"):      # INIT — нет обращения CMC; OM — смена знаменателя/тикера в 2026 г.
            continue
        a = analyze(s, sym, s["exp"])
        if not a:
            print(f"  {sym}: нет данных/обращения")
            continue
        m = a["ut_d"] / 30.4
        c = {th: sum(f >= th for f, *_ in a["e1"]) / m for th in THR}
        c2 = {th: sum(f >= th for f, _ in a["e2"]) / m for th in THR}
        for th in THR:
            tot[("e1", th)] += c[th]; tot[("e2", th)] += c2[th]
        top = a["e1"][0]
        print(f"  {sym:5s} | {a['ut_d']:.0f} | {100 * a['queue']:.2f}% | {c[0.0005]:.1f} | {c[0.001]:.1f} | {c[0.005]:.1f} | "
              f"{c2[0.001]:.1f} | {c2[0.005]:.1f} | {100 * top[0]:.2f}% ({fmt_t(top[1] * DAY)})")
        out.setdefault("now", []).append(dict(sym=sym, ut_d=a["ut_d"], queue=a["queue"],
                                              e1=[(f, d) for f, d, _ in a["e1"] if f >= 0.0005]))
    print(f"  ВСЕГО в месяц: E1 ≥0,05% {tot[('e1', 0.0005)]:.0f}, ≥0,1% {tot[('e1', 0.001)]:.0f}, ≥0,5% {tot[('e1', 0.005)]:.0f}, "
          f"≥1% {tot[('e1', 0.01)]:.0f}; E2 ≥0,1% {tot[('e2', 0.001)]:.0f}, ≥0,5% {tot[('e2', 0.005)]:.0f}")
    json.dump(out, open(f"{OUT}/cosmos_events.json", "w"))


if __name__ == "__main__":
    main()
