"""s275 — замысел Г3 «общий держатель»: одновременные выносы нескольких монет вне рыночного движения, отрезок замысла
01.10.2022–01.10.2023 (часовые шаги, топ-100, OI — s230/metrics). Описательно: сколько таких часов, размер кластеров,
средний остаток за следующие 4 ч у монет кластера и у одиночных выносов. Комиссии, стопы и правила выхода не считаются.

Вынос монеты в час T: OI в монетах за час ≤ −5% и остаток e1 за час ≤ −2% (e1 — после BTC и индекса альтов,
коэффициенты с прошлого месяца). «Спокойный рынок»: |индекс альтов за час| ≤ 1% и |BTC за час| ≤ 1%.
Кластер — ≥ 3 выноса в один час спокойного рынка. Зеркало — вынос шортов (OI ≤ −5%, остаток ≥ +2%).
Запуск: из /home/user/mc_data — python3 -I <repo>/research/s275/study/cond_oi_design.py → OUT/cond_oi_design.txt"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common275 import DESIGN, H, OUT, load_k, panel, perps, ts, universe  # noqa: E402
from leadlag_design import alt_factor, month_starts  # noqa: E402

PER = "2022–2024"
LINES = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LINES.append(s)


def oi_hourly(p, T):
    f = f"s230/metrics/{p}.npy"
    if not os.path.exists(f):
        return None
    a = np.load(f, allow_pickle=True)
    if a.ndim != 2 or not len(a):
        return None
    t = a[:, 0].astype(np.int64); oi = a[:, 1].astype(float)
    m = (t % 3600) == 0
    s = dict(zip(t[m], oi[m]))
    return np.array([s.get(int(x), np.nan) for x in T])


def main():
    K = load_k(PER)
    P = perps(K)
    LR = universe(K, P, PER)
    pidx = {p: k for k, p in enumerate(P)}
    iB = pidx["BTC"]
    t0, t1 = DESIGN
    T, LC, QV = panel(K, P, t0, t1, H)
    R = np.full(LC.shape, np.nan); R[:, 1:] = LC[:, 1:] - LC[:, :-1]
    alt = alt_factor(R, QV, iB, 24)
    btc = R[iB]
    X = np.column_stack([np.ones(R.shape[1]), btc, alt])
    calm = (np.abs(alt) <= 0.01) & (np.abs(btc) <= 0.01)
    MS = month_starts()
    ev_rows = []
    oi_cache = {}
    for mi in range(len(MS) - 1):
        a0, a1 = MS[mi], MS[mi + 1]
        f0 = MS[mi - 1] if mi > 0 else ts("2022-10-01")
        ev = (T > a0) & (T <= a1); fit = (T > f0) & (T <= a0)
        U = [p for p in sorted(LR.get(int(a0 // 86400 * 86400), ())) if p in pidx and p != "BTC"]
        for p in U:
            y = R[pidx[p]]
            ok = fit & np.isfinite(y) & np.isfinite(X).all(1)
            if ok.sum() < 300:
                continue
            b, *_ = np.linalg.lstsq(X[ok], y[ok], rcond=None)
            e = y - X @ b
            if p not in oi_cache:
                oi_cache[p] = oi_hourly(p, T)
            oi = oi_cache[p]
            if oi is None:
                continue
            doi = np.full(len(T), np.nan); doi[1:] = oi[1:] / oi[:-1] - 1
            for i in np.flatnonzero(ev):
                if not (np.isfinite(doi[i]) and doi[i] <= -0.05 and np.isfinite(e[i]) and abs(e[i]) >= 0.02):
                    continue
                f = e[i + 1:i + 5]
                ev_rows.append((i, p, np.sign(e[i]), e[i], f.sum() if len(f) == 4 and np.isfinite(f).all() else np.nan,
                                bool(calm[i])))
    # ---- замысел Г3: перелёт выноса в час движения рынка ----
    g3 = []
    for mi in range(len(MS) - 1):
        a0, a1 = MS[mi], MS[mi + 1]
        f0 = MS[mi - 1] if mi > 0 else ts("2022-10-01")
        ev = (T > a0) & (T <= a1); fit = (T > f0) & (T <= a0)
        U = [p for p in sorted(LR.get(int(a0 // 86400 * 86400), ())) if p in pidx and p != "BTC"]
        for p in U:
            y = R[pidx[p]]
            ok = fit & np.isfinite(y) & np.isfinite(X).all(1)
            if ok.sum() < 300 or oi_cache.get(p) is None:
                continue
            b, *_ = np.linalg.lstsq(X[ok], y[ok], rcond=None)
            e = y - X @ b
            oi = oi_cache[p]
            doi = np.full(len(T), np.nan); doi[1:] = oi[1:] / oi[:-1] - 1
            for i in np.flatnonzero(ev):
                for side, mk in ((-1, alt[i] <= -0.01 or btc[i] <= -0.01), (1, alt[i] >= 0.01 or btc[i] >= 0.01)):
                    if not mk or not np.isfinite(e[i]) or e[i] * side < 0.015:
                        continue
                    fl = np.isfinite(doi[i]) and doi[i] <= -0.05
                    fl3 = np.isfinite(doi[i]) and doi[i] <= -0.03
                    out = []
                    for h in (2, 4, 8):
                        f = e[i + 1:i + 1 + h]
                        out.append(-side * f.sum() if len(f) == h and np.isfinite(f).all() else np.nan)
                    g3.append((side, fl, e[i] * side, *out, T[i], fl3))
    G = np.array(g3, dtype=float)
    months = 11
    say("s275 — выносы по OI и кластеры «общего держателя», отрезок замысла 01.10.2022–01.10.2023 (топ-100)")
    say("\n## Замысел Г3: час движения рынка (индекс альтов или BTC ≥ 1% в одну сторону), монета перелетела рынок")
    say("на ≥ 2% остатка в ту же сторону; «вынос» — ещё и OI за час ≤ −5%. Возврат > 0 — остаток против перелёта.")
    for side, nm in ((-1, "рынок вниз, монета ниже беты"), (1, "рынок вверх, монета выше беты")):
        for fl, nf in ((True, "с выносом OI"), (False, "без выноса OI")):
            m = (G[:, 0] == side) & (G[:, 1] == float(fl)) & (G[:, 2] >= 0.02)
            if m.sum() < 5:
                continue
            g = G[m]
            hours = len(np.unique(g[:, 6]))
            say(f"  {nm}, {nf}: n {m.sum()} ({m.sum() / months:.0f} в мес.; часов {hours}, {hours / months:.0f} в мес.), "
                f"перелёт медиана {np.median(g[:, 2]):.2%}; возврат 2 ч {np.nanmean(g[:, 3]):+.2%}, 4 ч {np.nanmean(g[:, 4]):+.2%} "
                f"(медиана {np.nanmedian(g[:, 4]):+.2%}, СО {np.nanstd(g[:, 4]):.2%}), 8 ч {np.nanmean(g[:, 5]):+.2%}")
    say("  варианты (рынок вниз): порог остатка и OI → n в мес., разных часов в мес., возврат 4 ч среднее / медиана")
    for thr_e in (0.015, 0.02, 0.03):
        for col, nm_oi in ((1, "OI ≤ −5%"), (7, "OI ≤ −3%")):
            m = (G[:, 0] == -1) & (G[:, 7 if col == 7 else 1] == 1) & (G[:, 2] >= thr_e)
            if m.sum() < 5:
                continue
            g = G[m]
            say(f"    остаток ≤ −{thr_e:.1%}, {nm_oi}: {m.sum() / months:.0f} в мес., часов {len(np.unique(g[:, 6])) / months:.0f}"
                f" в мес.; 4 ч {np.nanmean(g[:, 4]):+.2%} / {np.nanmedian(g[:, 4]):+.2%}")
    months = 11
    for sgn, name in ((-1, "вынос лонгов (остаток ≤ −2%)"), (1, "вынос шортов (остаток ≥ +2%)")):
        rows = [r for r in ev_rows if r[2] == sgn]
        say(f"\n## {name}: всего {len(rows)} ({len(rows) / months:.0f} в мес.), в спокойные часы "
            f"{sum(r[5] for r in rows)} ({sum(r[5] for r in rows) / months:.0f} в мес.)")
        by_h = {}
        for r in rows:
            if r[5]:
                by_h.setdefault(r[0], []).append(r)
        sizes = np.array([len(v) for v in by_h.values()])
        if len(sizes):
            say(f"  часов спокойного рынка с выносами: {len(sizes)}; размер: 1 — {np.sum(sizes == 1)}, 2 — {np.sum(sizes == 2)}, "
                f"≥ 3 — {np.sum(sizes >= 3)} (монет в них {sizes[sizes >= 3].sum()}; {np.sum(sizes >= 3) / months:.1f} часа в мес.)")
        for lab, sel in (("кластер ≥ 3", lambda v: len(v) >= 3), ("2 монеты", lambda v: len(v) == 2),
                         ("одиночный", lambda v: len(v) == 1)):
            ys = np.array([r[4] * (-sgn) for v in by_h.values() if sel(v) for r in v if np.isfinite(r[4])])
            if len(ys) >= 5:
                say(f"  {lab}: n {len(ys)}; остаток за следующие 4 ч против выноса (возврат > 0): среднее {np.mean(ys):+.2%}, "
                    f"медиана {np.median(ys):+.2%}, СО {np.std(ys):.2%}")
        ys = np.array([r[4] * (-sgn) for r in rows if not r[5] and np.isfinite(r[4])])
        if len(ys):
            say(f"  в неспокойные часы: n {len(ys)}; среднее {np.mean(ys):+.2%}, медиана {np.median(ys):+.2%}")
    open(f"{OUT}/cond_oi_design.txt", "w").write("\n".join(LINES) + "\n")


if __name__ == "__main__":
    main()
