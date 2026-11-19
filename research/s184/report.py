"""s184 — сводка Г1 (доля корейской розницы, пары с контролем) и Г2/Г4 (OI) по трём периодам из s184_<период>.pkl.
Запуск: python3 <repo>/research/s184/report.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s182"))
import common182 as C  # noqa: E402

DAY, OUT = C.DAY, C.OUT


def load():
    return {per: pd.read_pickle(f"{OUT}/s184_{per}.pkl") for per in C.PER}


def pairs(R, col="net"):
    a = R[R.grp == "g1"].set_index(["d0", "k"])[[col, "t"]]
    b = R[R.grp == "g1_ctl"].set_index(["d0", "k"])[[col]]
    z = a.join(b, rsuffix="_c", how="inner")
    return z[col] - z[col + "_c"], z.t


def g1(A):
    print("Г1 — «монета корейской розницы»: 5 альтов с наибольшей долей Upbit + Bithumb (≥ 15%), без корейских журналов и 🛒\n"
          "за 7 сут, f7 > −0,3% → шорт 7 сут, стоп 25%; контроль (а) — пары с долей ≤ 3% по рангам оборота и волатильности\n")
    parts, parts_h = [], []
    for per, R in A.items():
        g, c = R[R.grp == "g1"], R[R.grp == "g1_ctl"]
        d, t = pairs(R); dh, _ = pairs(R, "hed")
        m, tt, n = C.ct(d, t); mh, th, _ = C.ct(dh, t)
        se = abs(m / tt) if tt else np.nan; seh = abs(mh / th) if th else np.nan
        parts.append((m, se, n)); parts_h.append((mh, seh, n))
        print(f"{per}:")
        print(f"  корзина     {C.line(g, per)}")
        print(f"  контроль (а) {C.line(c, per)}")
        print(f"  пары: n={n}, Δ = {m:+.2%} (t {tt:+.1f}); с хеджем Δ = {mh:+.2%} (t {th:+.1f})")
    m, t = C.combine(parts); mh, th = C.combine(parts_h)
    print(f"\nвместе: Δ = {m:+.2%} (t {t:+.1f}); с хеджем Δ = {mh:+.2%} (t {th:+.1f})")
    print("\nРазрезы (средний доход части; Δ к контролю (а) — разность средних):")
    lab = {"g1_t20": "порог 20%", "g1_t25": "порог 25%", "g1_noveto": "без вето по фандингу",
           "g1_withj": "с журналами", "g1_spot": "контроль (б): доля спота Binance"}
    for grp, name in lab.items():
        out = []
        for per, R in A.items():
            x, c = R[R.grp == grp], R[R.grp == "g1_ctl"]
            z = pd.concat([x.assign(e=1), c.assign(e=0)])
            d, se = C.diff(z.net, z.e, z.t)
            out.append(f"n={len(x):4d} {x.net.mean():+.2%} Δ {d:+.2%} (t {d / se:+.1f})")
        print(f"  {name:34s} " + " | ".join(out))
    out = []
    for per, R in A.items():
        g, s = R[R.grp == "g1"], R[R.grp == "g1_spot"]
        z = pd.concat([g.assign(e=1), s.assign(e=0)])
        d, se = C.diff(z.net, z.e, z.t)
        out.append(f"Δ {d:+.2%} (t {d / se:+.1f})")
    print(f"  {'корзина − контроль (б)':34s} " + " | ".join(out))
    sub = {"доля 15–25%": lambda g: (g.kshare7 < 0.25), "доля 25–35%": lambda g: (g.kshare7 >= 0.25) & (g.kshare7 < 0.35),
           "доля ≥ 35%": lambda g: g.kshare7 >= 0.35, "премия Кореи > 0": lambda g: g.kprem7 > 0,
           "премия Кореи ≤ 0": lambda g: g.kprem7 <= 0, "сверх нормы (kabn > 0)": lambda g: g.kabn > 0,
           "Upbit больше Bithumb": lambda g: g.upbit > g.bithumb, "Bithumb больше Upbit": lambda g: g.upbit <= g.bithumb,
           "2025 г.": lambda g: (g.t >= C.ts("2025-01-01")) & (g.t < C.ts("2026-01-01"))}
    for name, f in sub.items():
        out = []
        for per, R in A.items():
            g, c = R[R.grp == "g1"], R[R.grp == "g1_ctl"]
            x = g[f(g)]
            if len(x) < 5:
                out.append(f"n={len(x):4d}"); continue
            z = pd.concat([x.assign(e=1), c.assign(e=0)])
            d, se = C.diff(z.net, z.e, z.t)
            out.append(f"n={len(x):4d} {x.net.mean():+.2%} Δ {d:+.2%} (t {d / se:+.1f})")
        print(f"  {name:34s} " + " | ".join(out))
    out = []
    for per, R in A.items():
        g, c = R[R.grp == "g1"], R[R.grp == "g1_ctl"]
        top = g.s.value_counts().index[:3]
        x = g[~g.s.isin(top)]
        z = pd.concat([x.assign(e=1), c.assign(e=0)])
        d, se = C.diff(z.net, z.e, z.t)
        w = 1 / g.s.map(g.s.value_counts())
        out.append(f"без {', '.join(top)}: {x.net.mean():+.2%} Δ {d:+.2%} (t {d / se:+.1f}); вес 1/недель {np.average(g.net, weights=w):+.2%}")
    print("  без трёх частых монет; вес 1/(недель монеты):")
    for o, per in zip(out, A):
        print(f"    {per}: {o}")


def g2(A):
    print("\n\nГ2 — «уход интереса»: OI за 7 сут ≤ −15% при |ход| ≤ 10% → шорт 5 монет с наибольшим падением OI, 7 сут, стоп 25%;\n"
          "контроль — OI ≥ +15% при той же цене\n")
    parts, parts_h = [], []
    for per, R in A.items():
        f, g = R[R.grp == "g2_fall"], R[R.grp == "g2_grow"]
        if not len(f):
            print(f"{per}: нет срезов с OI"); continue
        z = pd.concat([f.assign(e=1), g.assign(e=0)])
        d, se = C.diff(z.net, z.e, z.t); dh, seh = C.diff(z.hed, z.e, z.t)
        parts.append((d, se, len(f))); parts_h.append((dh, seh, len(f)))
        rnd = R[R.grp == "g2_rand"]
        z2 = pd.concat([f.assign(e=1), rnd.assign(e=0)])
        d2, se2 = C.diff(z2.net, z2.e, z2.t)
        weeks = f.d0.nunique()
        print(f"{per} (срезов с корзиной {weeks}):")
        print(f"  падение OI {C.line(f, per)}")
        print(f"  рост OI    {C.line(g, per)}")
        print(f"  случайные  {C.line(rnd, per)}")
        print(f"  Δ падение − рост = {d:+.2%} (t {d / se:+.1f}); с хеджем {dh:+.2%} (t {dh / seh:+.1f}); "
              f"падение − случайные {d2:+.2%} (t {d2 / se2:+.1f})")
    m, t = C.combine(parts); mh, th = C.combine(parts_h)
    print(f"\nвместе: Δ = {m:+.2%} (t {t:+.1f}); с хеджем Δ = {mh:+.2%} (t {th:+.1f})")
    print("\nРазрезы (средний доход; Δ к контролю «рост OI»):")
    for grp, name in (("g2_fall10", "порог −10%"), ("g2_fall25", "порог −25%"), ("g2_usd", "OI в $")):
        out = []
        for per, R in A.items():
            x, c = R[R.grp == grp], R[R.grp == "g2_grow"]
            if len(x) < 5:
                out.append(f"n={len(x)}"); continue
            z = pd.concat([x.assign(e=1), c.assign(e=0)])
            d, se = C.diff(z.net, z.e, z.t)
            out.append(f"n={len(x):4d} {x.net.mean():+.2%} Δ {d:+.2%} (t {d / se:+.1f})")
        print(f"  {name:28s} " + " | ".join(out))
    sub = {"f7 ≥ 0": lambda g: g.f7 >= 0, "f7 < 0": lambda g: g.f7 < 0, "OI / оборот выше медианы": lambda g: g.oiqv_hi,
           "OI / оборот ниже медианы": lambda g: ~g.oiqv_hi.astype(bool), "оборот ≥ 20 млн $": lambda g: g.qv7 >= 2e7}
    for name, fn in sub.items():
        out = []
        for per, R in A.items():
            f, c = R[R.grp == "g2_fall"], R[R.grp == "g2_grow"]
            x = f[fn(f)] if len(f) else f
            if len(x) < 5:
                out.append(f"n={len(x)}"); continue
            z = pd.concat([x.assign(e=1), c.assign(e=0)])
            d, se = C.diff(z.net, z.e, z.t)
            out.append(f"n={len(x):4d} {x.net.mean():+.2%} Δ {d:+.2%} (t {d / se:+.1f})")
        print(f"  {name:28s} " + " | ".join(out))
    out = []
    for per, R in A.items():
        x, c = R[R.grp == "g4_cover"], R[R.grp == "g4_build"]
        if len(x) < 5:
            out.append(f"n={len(x)}"); continue
        z = pd.concat([x.assign(e=1), c.assign(e=0)])
        d, se = C.diff(z.net, z.e, z.t)
        out.append(f"рост без денег n={len(x)} {x.net.mean():+.2%}, на новых n={len(c)} {c.net.mean():+.2%}, Δ {d:+.2%} (t {d / se:+.1f})")
    print("  Г4 (减仓上涨 против 增仓上涨):")
    for o, per in zip(out, A):
        print(f"    {per}: {o}")


if __name__ == "__main__":
    A = load()
    g1(A)
    g2(A)
