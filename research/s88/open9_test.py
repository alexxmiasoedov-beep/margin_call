"""s88 — «обещанные 9 утра»: фьючерс за час 00:00–01:00 UTC (открытие дня Upbit, 09:00 по Корее) вырос на ≥ 7% при доле
Кореи в обороте часа ≥ 20% → шорт на закрытии в 01:00 UTC; тейк 10 / стоп 25 / 48 ч (основной), 24 ч и 4 ч со стопом 15%.
Контроль часа — то же правило в остальные часы (не чаще раза в сутки на монету); плацебо — та же монета за 45/90/135 сут
в тот же час. Гипотеза — ВЫВОДЫ.md, записана до расчёта. Запуск из папки с данными: python3 <путь>/s88/open9_test.py"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, live, trade  # noqa: E402
from oi_test import CUT, DAY, ct, idx_at  # noqa: E402

EXITS = {"S_10_25": dict(tp=0.10, sl=0.25, hold_h=48), "S_24h": dict(tp=None, sl=0.15, hold_h=24),
         "S_4h": dict(tp=None, sl=0.15, hold_h=4)}
R_MIN, SH_MIN = 0.05, 0.10          # нижние пороги вариантов; основное правило — 7% и 20%


def overlap_sets():
    """Входы действующих журналов: 🔝 и 👀 — за 7 сут до события, 🇰🇷 и 🛒 — за сутки (как в s86)."""
    S65 = pd.read_pickle("s65/trades.pkl"); S83 = pd.read_pickle("s83/trades.pkl")
    S49 = pd.read_pickle("s49/trades.pkl"); S49 = S49[S49.share >= 0.259]
    S20 = pd.read_pickle("s20/trades.pkl"); S20 = S20[S20.journal == "🇰🇷"]
    wk, dy = {}, {}
    for s, t in list(zip(S65.s, S65.t)) + list(zip(S83.s, S83.t)):
        wk.setdefault(s, []).append(t)
    for s, t in list(zip(S49.s, S49.t)) + list(zip(S20.s, S20.te)):
        dy.setdefault(s, []).append(t)
    return {s: np.array(v) for s, v in wk.items()}, {s: np.array(v) for s, v in dy.items()}


def events():
    KP = pickle.load(open("s15/kr_panel.pkl", "rb"))
    wk, dy = overlap_sets()
    rows = []
    for s, d in KP.items():
        lo, hi = live(s)
        x = d[(d.r1 >= R_MIN) & (d.share >= SH_MIN) & (d["T"] >= lo + DAY) & (d["T"] <= hi)]
        for T, j, r1, sh in zip(x["T"].values, x.j.values, x.r1.values, x.share.values):
            T = int(T); open9 = T % DAY == 3600
            a, b = wk.get(s, np.zeros(0)), dy.get(s, np.zeros(0))
            r = dict(s=s, t=T, open9=open9, r1=float(r1), share=float(sh),
                     ov=bool(((a <= T) & (a >= T - 7 * DAY)).any() or ((b <= T) & (b >= T - DAY)).any()))
            for nm, kw in EXITS.items():
                y = trade(s, int(j), **kw)
                r[nm] = y["net"] if y else np.nan
                p = [z["net"] for dd in (45, 90, 135) if (k := idx_at(s, T - dd * DAY)) is not None and (z := trade(s, k, **kw))]
                r["pl_" + nm] = np.mean(p) if p else np.nan
            rows.append(r)
    return pd.DataFrame(rows)


def line(lab, x0, col, months):
    x = x0[x0[col].notna()]
    if len(x) < 8:
        print(f"  {lab:34s} {col:7s} n={len(x)}")
        return None
    m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
    h1, h2 = x[x.t < CUT], x[x.t >= CUT]
    (m1, t1, _), (m2, t2, _) = ct(h1[col], h1.t), ct(h2[col], h2.t)
    print(f"  {lab:34s} {col:7s} n={n:5d} ({n / months:5.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
          f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f}) | плацебо {x['pl_' + col].mean():+6.2%},"
          f" разница {dp:+6.2%} (t {tp:+4.1f})")
    return m, (abs(m / t) if t else np.nan)


def pick(X, rr, sh, hours="other"):
    """События с порогами rr и sh: «open» — только час открытия; «other» — остальные часы, «all» — любые;
    вне часа открытия не чаще раза в сутки на монету (кулдаун по тем же порогам)."""
    x = X[(X.r1 >= rr) & (X.share >= sh)]
    if hours == "open":
        return x[x.open9]
    if hours == "other":
        x = x[~x.open9]
    keep, last = [], {}
    for i, s, t in zip(x.index, x.s.values, x.t.values):
        if t - last.get(s, -10 ** 18) >= DAY:
            keep.append(i); last[s] = t
    return x.loc[keep]


def main():
    X = events().sort_values("t").reset_index(drop=True)
    X.to_pickle("s88/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    A, O = pick(X, 0.07, 0.20, "open"), pick(X, 0.07, 0.20, "other")
    print(f"Событий «9 утра» (рост ≥ 7%, доля ≥ 20%): {len(A)} ({len(A) / months:.1f} в месяц), без входов журналов "
          f"{(~A.ov).sum()} ({(~A.ov).sum() / months:.1f} в месяц); в другие часы: {len(O)} ({len(O) / months:.1f} в месяц)")
    for col in EXITS:
        print(f"\n{col}")
        r9 = line("9 утра, без журналов (основная)", A[~A.ov], col, months)
        line("9 утра, все", A, col, months)
        ro = line("другие часы, без журналов", O[~O.ov], col, months)
        if r9 and ro:
            d = r9[0] - ro[0]; se = np.hypot(r9[1], ro[1])
            print(f"  разница «9 утра» − другие часы: {d:+6.2%} (t {d / se:+4.1f})")
    print("\nВарианты порогов (основная группа «9 утра», S_10_25):")
    for rr in (0.05, 0.07, 0.10):
        for sh in (0.10, 0.20, 0.30):
            x = pick(X, rr, sh, "open")
            line(f"рост ≥ {rr:.0%}, доля ≥ {sh:.0%}", x[~x.ov], "S_10_25", months)
    print("\nПосле расчёта (не записано заранее): рост ≥ 5%, доля ≥ 20%, без журналов, S_10_25 — час открытия, другие часы,"
          " любой час:")
    for hh in ("open", "other", "all"):
        x = pick(X, 0.05, 0.20, hh)
        line(f"{hh}", x[~x.ov], "S_10_25", months)
    print("\nЧас открытия против соседних часов (без журналов, рост ≥ 7%, доля ≥ 20%, S_10_25):")
    Y = pick(X, 0.07, 0.20, "all"); Y = Y[~Y.ov].copy()
    Y["h"] = ((Y.t - 3600) % DAY) // 3600
    for h, g in Y.groupby("h"):
        line(f"час {h:02d}–{h + 1:02d} UTC", g, "S_10_25", months)


if __name__ == "__main__":
    main()
