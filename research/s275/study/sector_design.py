"""s275 — секторные корзины и «монета против своей корзины» на отрезке замысла 01.10.2022–01.10.2023 (часовые шаги).
Только описательная статистика (автокорреляции, наклоны «прошлое → будущее», доля общей дисперсии), доходы не считаются.

- вселенная месяца — 200 перпов с наибольшим оборотом за 30 сут до начала месяца (шире, чтобы в секторах было ≥ 4 монет);
- корзина сектора — равный вес членов вселенной сектора (≥ 4); остаток корзины к рынку — после BTC и индекса альтов
  (коэффициенты с прошлого месяца);
- спред «монета − корзина сектора без монеты» (сырой, без коэффициентов) — то, что торгует пара «монета / сектор»;
- группы: сектор (Binance underlyingSubType и др., sectors.csv), подсектор, сеть (кроме Ethereum).
Запуск: из /home/user/mc_data — python3 -I <repo>/research/s275/study/sector_design.py → OUT/sector_design.txt"""
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common275 import DESIGN, H, OUT, load_k, panel, perps, sectors, ts, universe  # noqa: E402
from leadlag_design import alt_factor, month_starts  # noqa: E402

PER = "2022–2024"
LINES = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LINES.append(s)


def pf(x, k, h):
    c = np.concatenate([[0.0], np.cumsum(np.where(np.isfinite(x), x, 0.0))])
    bad = np.concatenate([[0], np.cumsum(~np.isfinite(x))])
    idx = np.arange(k, len(x) - h + 1)                      # начало — каждый час (будущие окна перекрываются)
    ok = ((bad[idx] - bad[idx - k]) == 0) & ((bad[idx + h] - bad[idx]) == 0)
    return (c[idx] - c[idx - k])[ok], (c[idx + h] - c[idx])[ok]


def main():
    t_s = time.time()
    K = load_k(PER)
    P = perps(K)
    SEC = sectors()
    LR = universe(K, P, PER, top=200)
    pidx = {p: k for k, p in enumerate(P)}
    iB = pidx["BTC"]
    t0, t1 = DESIGN
    T, LC, QV = panel(K, P, t0, t1, H)
    R = np.full(LC.shape, np.nan); R[:, 1:] = LC[:, 1:] - LC[:, :-1]
    alt = alt_factor(R, QV, iB, 24)
    btc = R[iB]
    X = np.column_stack([np.ones(R.shape[1]), btc, alt])
    MS = month_starts()
    KH = [(1, 1), (1, 4), (4, 4), (4, 8), (8, 8), (24, 24)]
    acc = {}
    sizes = {}

    def addpf(key, x):
        for k, h in KH:
            a, b = pf(x, k, h)
            s = acc.setdefault((key[0], key[1], k, h), np.zeros(4))
            s += [np.sum(a * b), np.sum(a * a), np.sum(b * b), len(a)]

    for mi in range(len(MS) - 1):
        a0, a1 = MS[mi], MS[mi + 1]
        f0 = MS[mi - 1] if mi > 0 else ts("2022-10-01")
        ev = (T > a0) & (T <= a1); fit = (T > f0) & (T <= a0)
        U = [p for p in sorted(LR.get(int(a0 // 86400 * 86400), ())) if p in pidx and p != "BTC"]
        U = [p for p in U if np.isfinite(R[pidx[p], ev]).mean() >= 0.9 and np.isfinite(R[pidx[p], fit]).mean() >= 0.9]
        liq = {p: QV[pidx[p], fit].sum() for p in U}
        rank = {p: r for r, p in enumerate(sorted(U, key=lambda p: -liq[p]))}
        groups = {}
        for p in U:
            d = SEC.get(p, {})
            if d.get("sector"):
                groups.setdefault(("сектор", d["sector"]), []).append(p)
            if d.get("subsector"):
                groups.setdefault(("подсектор", d["subsector"]), []).append(p)
            if d.get("eco") and d["eco"] not in ("Ethereum",):
                groups.setdefault(("сеть", d["eco"]), []).append(p)
        for (kind, name), mem in groups.items():
            if len(mem) < 4:
                continue
            sizes.setdefault((kind, name), []).append(len(mem))
            M = np.clip(R[[pidx[p] for p in mem]], -0.5, 0.5)
            with np.errstate(all="ignore"):
                bk = np.nanmean(M, axis=0)
            ok = fit & np.isfinite(bk) & np.isfinite(X).all(1)
            if ok.sum() < 300:
                continue
            b, *_ = np.linalg.lstsq(X[ok], bk[ok], rcond=None)
            e = (bk - X @ b)[ev]
            addpf((kind, "корзина к рынку"), e)
            v_r = np.nanvar(bk[ev]); v_e = np.nanvar(e)
            acc.setdefault((kind, "R2 корзины рынком"), []).append(1 - v_e / v_r)
            for j, p in enumerate(mem):
                others = np.delete(M, j, axis=0)
                with np.errstate(all="ignore"):
                    ob = np.nanmean(others, axis=0)
                d = (R[pidx[p]] - ob)[ev]
                grp = "топ-30" if rank[p] < 30 else ("31–100" if rank[p] < 100 else "101–200")
                addpf((kind, f"монета − корзина, {grp}"), d)
                # доля дисперсии монеты, снимаемая корзиной сектора сверх рынка (вне выборки)
                y = R[pidx[p]]
                X2 = np.column_stack([X, ob])
                okf = fit & np.isfinite(y) & np.isfinite(X2).all(1)
                if okf.sum() < 300:
                    continue
                b1, *_ = np.linalg.lstsq(X[okf], y[okf], rcond=None)
                b2, *_ = np.linalg.lstsq(X2[okf], y[okf], rcond=None)
                e1 = (y - X @ b1)[ev]; e2 = (y - X2 @ b2)[ev]
                oke = np.isfinite(e1) & np.isfinite(e2)
                if oke.sum() > 300:
                    acc.setdefault((kind, f"R2 сверх рынка, {grp}"), []).append(1 - np.var(e2[oke]) / np.var(e1[oke]))
        say(f"  месяц {time.strftime('%Y-%m', time.gmtime(a0))}: вселенная {len(U)}, групп ≥ 4: "
            f"{sum(1 for v in groups.values() if len(v) >= 4)} ({time.time() - t_s:.0f} с)")
    say("\n## Размер групп (в среднем членов во вселенной топ-200 за месяц, группы с ≥ 4 членами)")
    for kind in ("сектор", "подсектор", "сеть"):
        items = sorted(((n, np.mean(v)) for (k, n), v in sizes.items() if k == kind), key=lambda x: -x[1])
        say(f"  {kind}: " + ", ".join(f"{n} {m:.1f}" for n, m in items))
    say("\n## Доля дисперсии (вне выборки, медиана)")
    for key in sorted(k for k in acc if isinstance(acc[k], list)):
        v = np.array(acc[key])
        say(f"  {key[0]} — {key[1]}: медиана {np.nanmedian(v):+.3f}, среднее {np.nanmean(v):+.3f}, доля > 0 "
            f"{np.nanmean(v > 0):.2f} (n={len(v)})")
    say("\n## Наклон «прошлые k ч → следующие h ч» (b = Σxy/Σx²; ρ; амплитуда для хода 2σ)")
    for key in sorted({k[:2] for k in acc if not isinstance(acc[k], list)}):
        parts = []
        for k, h in KH:
            s = acc.get((key[0], key[1], k, h))
            if s is None or s[1] <= 0:
                continue
            b = s[0] / s[1]; rho = s[0] / np.sqrt(s[1] * s[2]); sk = np.sqrt(s[1] / s[3])
            parts.append(f"{k}→{h}: b {b:+.3f} (ρ {rho:+.3f}; 2σ {2 * sk:.2%} → {b * 2 * sk:+.2%}; n {s[3]:.0f})")
        say(f"  {key[0]} — {key[1]}: " + "; ".join(parts))
    open(f"{OUT}/sector_design.txt", "w").write("\n".join(LINES) + "\n")


if __name__ == "__main__":
    main()
