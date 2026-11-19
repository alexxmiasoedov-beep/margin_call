"""s182 Г2 — двойник 🐋 по происхождению токенов (гипотеза — ВЫВОДЫ.md, записана до расчёта).
Входы 🐋 по правилу бота (s167 live_variant, вариант B): первый у монеты за 48 ч завод на адреса Binance ≥ 0,5% обращения,
вход на закрытии первой 15-мин свечи не раньше чем через 15 мин после блока, ход фьючерса за 24 ч −5…+5%, фьючерс старше
суток; шорт 24 ч, стоп +25%; хедж — индекс альтов s103 на фактический срок; плацебо — та же монета за 45/90/135 сут.
Происхождение — s182_origin.pkl (origin_all.py). Событие — «не с рынка» или «долгий держатель», контроль — «с рынка».
Запуск из /home/user/mc_data: [MC_K=… MC_F=…] python3 <repo>/research/s182/g2.py <период>; сводка: … g2.py report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "s139"))
sys.path.insert(0, os.path.join(HERE, "..", "s142"))
import common182 as C  # noqa: E402

DAY, OUT = C.DAY, C.OUT


def first48(E):
    keep, last = np.zeros(len(E), bool), {}
    for i, r in enumerate(E.itertuples()):
        if r.t - last.get(r.perp, -10 ** 12) >= 48 * 3600:
            keep[i] = True; last[r.perp] = r.t
    return keep


def run(per):
    from common import K, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    t0, t1 = C.ts(C.PER[per][0]), C.ts(C.PER[per][1])
    T, I = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T, a - 900, "right")) - 1; j = int(np.searchsorted(T, b - 900, "right")) - 1
        return I[j] / I[i] - 1 if 0 <= i <= j < len(I) else np.nan

    E = pd.read_pickle(f"{OUT}/s160_events.pkl").sort_values("t").reset_index(drop=True)
    B = E[E.exch == "Binance"].copy()
    B = B[first48(B)]
    rows = []
    for r in B.itertuples():
        te = int(-(-(int(r.t) + 900) // 900) * 900)
        if not (t0 <= te < t1) or r.perp not in K:
            continue
        lo, hi = live(r.perp)
        if not np.isfinite(lo) or te < lo + DAY:
            continue
        i = idx_at(r.perp, te)
        if i is None or int(K[r.perp]["t"][i]) + 900 != te:
            continue
        j = idx_at(r.perp, te - DAY)
        if j is None or int(K[r.perp]["t"][j]) + 900 != te - DAY:
            continue
        r24 = float(K[r.perp]["c"][i]) / float(K[r.perp]["c"][j]) - 1
        if abs(r24) > 0.05:
            continue
        x = trade(r.perp, i, tp=None, sl=0.25, hold_h=24, side=-1)
        if not x:
            continue
        t_end = int(K[r.perp]["t"][i]) + 900 + int(x["bars"]) * 900
        pl = []
        for dd in (45, 90, 135):
            k = idx_at(r.perp, te - dd * DAY)
            y = trade(r.perp, k, tp=None, sl=0.25, hold_h=24, side=-1) if k is not None else None
            if y:
                pl.append(y["net"])
        rows.append(dict(s=r.perp, tx=r.tx, li=r.li, t=te, r24=r24, frac=r.frac, net=x["net"], why=x["why"],
                         hed=x["net"] + mv(te, t_end), pl=np.mean(pl) if pl else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s182_g2_{per}.pkl")
    print(per, "сделок 🐋", len(X), flush=True)


def report():
    import any_test as U  # noqa: E402  (s142: события 🔑⁺)
    O = pd.read_pickle(f"{OUT}/s182_origin.pkl")[["tx", "li", "end", "grp", "hops"]]
    Ev = U.events()
    kv = {k: g["T"].to_numpy(float) for k, g in Ev.groupby("key")}
    parts, parts_h, A = [], [], []
    print("Г2 — 🐋 «не с рынка или долгий держатель» против «с рынка»; шорт 24 ч, стоп 25%\n")
    for per in C.PER:
        X = pd.read_pickle(f"{OUT}/s182_g2_{per}.pkl").merge(O, on=["tx", "li"], how="left")
        X["grp"] = X.grp.fillna("нет в трассировке"); X["per"] = per
        X["unl"] = [bool(np.any(np.abs(kv.get(s, np.array([])) - t) <= 7 * DAY)) for s, t in zip(X.s, X.t)]
        A.append(X)
        ev = X.grp.isin(["не с рынка", "долгий держатель"]); c = X.grp == "с рынка"
        z = X[ev | c]
        d, se = C.diff(z.net, ev[z.index], z.t); dh, seh = C.diff(z.hed, ev[z.index], z.t)
        parts.append((d, se, int(ev.sum()))); parts_h.append((dh, seh, int(ev.sum())))
        print(f"{per}: все входы 🐋 {C.line(X, per)}")
        print(f"  не с рынка + долгий держатель {C.line(X[ev], per)}")
        print(f"  с рынка                       {C.line(X[c], per)}")
        print(f"  прочее                        {C.line(X[~ev & ~c], per)}  ({X[~ev & ~c].grp.value_counts().to_dict()})")
        print(f"  Δ = {d:+.2%} (t {d / se:+.1f}); с хеджем Δ = {dh:+.2%} (t {dh / seh:+.1f})")
    m, t = C.combine(parts); mh, th = C.combine(parts_h)
    print(f"\nвместе: Δ = {m:+.2%} (t {t:+.1f}); с хеджем Δ = {mh:+.2%} (t {th:+.1f})")
    A = pd.concat(A, ignore_index=True)
    print("\nРазрезы (Δ к контролю «с рынка», по периодам):")
    ev = A.grp.isin(["не с рынка", "долгий держатель"])
    sl = {"строго не с рынка": A.grp == "не с рынка", "долгий держатель": A.grp == "долгий держатель",
          "класс на шаге 1": ev & (A.hops == 1), "класс на шагах 2–3": ev & (A.hops >= 2),
          "в ±7 сут от разлока 🔑⁺": ev & A.unl, "вне разлоков": ev & ~A.unl,
          "безымянный после 3 шагов": A.grp == "прочее"}
    for lab, msk in sl.items():
        out = []
        for per in C.PER:
            x = A[A.per == per]; s = msk[A.per == per]; c = x.grp == "с рынка"
            z = x[s | c]
            d, se = C.diff(z.net, s[z.index], z.t)
            out.append(f"n={int(s.sum()):4d} {x[s].net.mean():+.2%} Δ {d:+.2%} (t {d / se:+.1f})" if s.sum() >= 5 else
                       f"n={int(s.sum()):4d}")
        print(f"  {lab:28s} " + " | ".join(out))
    A.to_pickle(f"{OUT}/s182_g2_all.pkl")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
