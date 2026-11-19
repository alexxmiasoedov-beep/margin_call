"""s203 — «след хеджа получателей перед разлоком» (Г5 s173): признаки фандинга и продаж на перпе за 14 сут до входа 🔑⁺
(s142) и разница дохода «со следом − без». Запись до расчёта — ВЫВОДЫ.md.
Запуск из /home/user/mc_data:
  python3 run.py 2024–2026
  MC_K=s117/k_oos.pkl MC_F=s117/fund_oos.pkl python3 run.py 2022–2024
  MC_K=s117/k_2020.pkl MC_F=s117/fund_2020.pkl python3 run.py 2020–2022
  python3 run.py report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
sys.path.insert(0, os.path.join(HERE, "..", "s182"))
DAY, OUT = 86400, "/home/user/mc_data"


def fund_mean(fr, a, b):
    """Средняя ставка на 8 ч за [a, b): сумма начислений / число 8-часовых отрезков."""
    if not len(fr):
        return np.nan
    m = (fr[:, 0] >= a) & (fr[:, 0] < b)
    return fr[m, 1].sum() / ((b - a) / (8 * 3600)) if m.any() else np.nan


def run(per):
    import fastbt as FB  # noqa: E402
    U = pd.read_pickle(f"{OUT}/s142_{per}.pkl").copy()
    F, S, fr_r, fr_b, bs = [], [], [], [], []
    for r in U.itertuples():
        t = int(r.t)
        fr = FB.funding(r.s) if r.s in FB.K else np.zeros((0, 2))
        R0, B0 = t - 14 * DAY, t - 42 * DAY
        a, b = fund_mean(fr, R0, t), fund_mean(fr, B0, R0)
        f = (np.isfinite(a) and a < 0) or (np.isfinite(a) and np.isfinite(b) and a - b <= -0.00005)
        sh = np.nan
        if r.s in FB.K:
            k = FB.K[r.s]
            tt = k["t"].astype(np.int64)
            m = (tt >= R0) & (tt + 900 <= t)
            qv = k["qv"][m].astype(float).sum()
            sh = k["tb"][m].astype(float).sum() / qv if qv > 0 else np.nan
        F.append(bool(f)); S.append(bool(np.isfinite(sh) and sh <= 0.49))
        fr_r.append(a); fr_b.append(b); bs.append(sh)
    U["F"], U["S"], U["fr_r"], U["fr_b"], U["buy"] = F, S, fr_r, fr_b, bs
    U["per"] = per
    U.to_pickle(f"{OUT}/s203_{per}.pkl")
    print(per, len(U), "F", int(U.F.sum()), "S", int(U.S.sum()), "F и S", int((U.F & U.S).sum()), flush=True)


def report():
    import common182 as C  # noqa: E402
    print("s203 — след хеджа перед разлоком: сделки 🔑⁺ (s142) со следом (фандинг упал И доля покупок перпа ≤ 49%) и без\n")
    parts = {k: [] for k in ("FS", "FS_h", "ForS", "F", "S")}
    ok_each = True
    for per in C.PER:
        U = pd.read_pickle(f"{OUT}/s203_{per}.pkl")
        U = U[U.net.notna()].copy()
        print(f"== {per}: сделок {len(U)} ({len(U) / C.months(per):.1f} в месяц) ==")
        for key, mask, name in (("FS", U.F & U.S, "след: F и S"), ("ForS", U.F | U.S, "F или S"),
                                ("F", U.F, "только признак F"), ("S", U.S, "только признак S")):
            x, y = U[mask], U[~mask]
            d, se = C.diff(U.net, mask, U.t)
            dh, seh = C.diff(U.hed, mask, U.t)
            print(f"  {name}: со следом n={len(x)} ({len(x) / C.months(per):.1f}/мес) {x.net.mean():+.2%}, без — n={len(y)} "
                  f"{y.net.mean():+.2%} | Δ {d:+.2%} (t {d / se:+.1f}); с хеджем Δ {dh:+.2%} (t {dh / seh:+.1f})")
            parts[key].append((d, se, len(U)))
            if key == "FS":
                parts["FS_h"].append((dh, seh, len(U)))
                ok_each &= bool(d > 0 and d / se >= 2)
        print()
    for key, name in (("FS", "след F и S"), ("FS_h", "след F и S, с хеджем"), ("ForS", "F или S"), ("F", "F"), ("S", "S")):
        d, t = C.combine(parts[key])
        print(f"Вместе, {name}: Δ {d:+.2%} (t {t:+.1f})")
    print("\nПорог (Δ > 0, t ≥ 2 в каждом периоде):", "пройден" if ok_each else "не пройден")


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report()
    else:
        run(sys.argv[1])
