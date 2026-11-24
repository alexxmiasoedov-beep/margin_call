"""s275 — связи «корзина альтов против BTC», «ETH против BTC» и зависимость возврата остатков от стресса рынка
на отрезке замысла 01.10.2022–01.10.2023 (часовые шаги). Только описательная статистика, доходы не считаются.

1) спред d = индекс альтов − β·BTC (β с прошлого месяца), ETH − β·BTC; наклоны «прошлые k ч → следующие h ч»;
2) наклон 1→4 ч остатков e1 монет (как stats_design) отдельно в часы стресса и в спокойные часы:
   стресс — |ход индекса альтов за прошлый час| в верхних 10% месяца модели или
   реализованная волатильность индекса за прошлые 4 ч в верхних 10%.
Запуск: из /home/user/mc_data — python3 -I <repo>/research/s275/study/market_design.py → OUT/market_design.txt"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common275 import DESIGN, H, OUT, load_k, panel, perps, ts, universe  # noqa: E402
from leadlag_design import alt_factor, month_starts  # noqa: E402
from sector_design import pf  # noqa: E402

PER = "2022–2024"
LINES = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LINES.append(s)


def main():
    K = load_k(PER)
    P = perps(K)
    LR = universe(K, P, PER)
    pidx = {p: k for k, p in enumerate(P)}
    iB = pidx["BTC"]; iE = pidx["ETH"]
    t0, t1 = DESIGN
    T, LC, QV = panel(K, P, t0, t1, H)
    R = np.full(LC.shape, np.nan); R[:, 1:] = LC[:, 1:] - LC[:, :-1]
    alt = alt_factor(R, QV, iB, 24)
    btc = R[iB]; eth = R[iE]
    MS = month_starts()
    KH = [(1, 1), (1, 4), (4, 4), (4, 8), (8, 8), (24, 24)]
    acc = {}

    def addpf(key, x):
        for k, h in KH:
            a, b = pf(x, k, h)
            s = acc.setdefault((key, k, h), np.zeros(4))
            s += [np.sum(a * b), np.sum(a * a), np.sum(b * b), len(a)]

    # реализованная волатильность индекса за прошлые 4 ч
    a2 = np.where(np.isfinite(alt), alt ** 2, 0.0)
    c = np.concatenate([[0.0], np.cumsum(a2)])
    rv4 = np.full(len(alt), np.nan); rv4[4:] = np.sqrt(c[4:-1] - c[:-5]) if len(alt) > 5 else np.nan
    for mi in range(len(MS) - 1):
        a0, a1 = MS[mi], MS[mi + 1]
        f0 = MS[mi - 1] if mi > 0 else ts("2022-10-01")
        ev = (T > a0) & (T <= a1); fit = (T > f0) & (T <= a0)
        for name, y in (("альты − β·BTC", alt), ("ETH − β·BTC", eth)):
            ok = fit & np.isfinite(y) & np.isfinite(btc)
            b = np.polyfit(btc[ok], y[ok], 1)
            addpf(name, (y - np.polyval(b, btc))[ev])
        # стресс: пороги по месяцу модели
        q_mv = np.nanquantile(np.abs(alt[fit]), 0.9); q_rv = np.nanquantile(rv4[fit], 0.9)
        U = [p for p in sorted(LR.get(int(a0 // 86400 * 86400), ())) if p in pidx and p != "BTC"]
        X = np.column_stack([np.ones(R.shape[1]), btc, alt])
        liq = {p: QV[pidx[p], fit].sum() for p in U}
        rank = {p: r for r, p in enumerate(sorted(U, key=lambda p: -liq[p]))}
        evi = np.flatnonzero(ev)
        for p in U:
            y = R[pidx[p]]
            ok = fit & np.isfinite(y) & np.isfinite(X).all(1)
            if ok.sum() < 300:
                continue
            b, *_ = np.linalg.lstsq(X[ok], y[ok], rcond=None)
            e = y - X @ b
            grp = "топ-30" if rank[p] < 30 else "31–100"
            # пары (остаток прошлого часа, сумма остатков следующих 4 ч) на каждом часе месяца оценки
            for i in evi[1:-4]:
                x0 = e[i]; f4 = e[i + 1:i + 5]
                if not (np.isfinite(x0) and np.isfinite(f4).all()):
                    continue
                stress = (abs(alt[i]) >= q_mv) or (rv4[i + 1] >= q_rv if np.isfinite(rv4[i + 1]) else False)
                key = (grp, "стресс" if stress else "спокойно")
                s = acc.setdefault(key, np.zeros(4))
                s += [x0 * f4.sum(), x0 * x0, f4.sum() ** 2, 1]
    say("s275 — корзины рынка и стресс, отрезок замысла 01.10.2022–01.10.2023")
    say("\n## Спреды рынка: наклон «прошлые k ч → следующие h ч» (амплитуда для хода 2σ)")
    for name in ("альты − β·BTC", "ETH − β·BTC"):
        parts = []
        for k, h in KH:
            s = acc[(name, k, h)]
            b = s[0] / s[1]; rho = s[0] / np.sqrt(s[1] * s[2]); sk = np.sqrt(s[1] / s[3])
            parts.append(f"{k}→{h}: b {b:+.3f} (ρ {rho:+.3f}; 2σ {2 * sk:.2%} → {b * 2 * sk:+.2%})")
        say(f"  {name}: " + "; ".join(parts))
    say("\n## Остатки монет e1: наклон «прошлый час → следующие 4 ч» в часы стресса и в спокойные часы")
    for grp in ("топ-30", "31–100"):
        for st in ("стресс", "спокойно"):
            s = acc.get((grp, st))
            if s is None:
                continue
            b = s[0] / s[1]; rho = s[0] / np.sqrt(s[1] * s[2]); sk = np.sqrt(s[1] / s[3])
            say(f"  {grp}, {st}: b {b:+.3f} (ρ {rho:+.3f}; n {s[3]:.0f}; 2σ часа {2 * sk:.2%} → {b * 2 * sk:+.2%})")
    open(f"{OUT}/market_design.txt", "w").write("\n".join(LINES) + "\n")


if __name__ == "__main__":
    main()
