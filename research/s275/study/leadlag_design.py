"""s275 — опережение-запаздывание между монетами на отрезке замысла 01.10.2022–01.10.2023 (15 мин и 1 ч).
Только описательная статистика рядов (кросс-корреляции и наклоны «ведущий сейчас → ведомый в следующий шаг»),
доходы сделок и правил не считаются.

- 15-мин и часовые лог-доходы (цена шага — закрытие последней 15-мин свечи шага со сделками);
- остатки e = r − a − b·BTC − c·альты, коэффициенты с прошлого календарного месяца, вселенная месяца — топ-100 по обороту;
- ведущие: BTC (сырые доходы) → альты; ETH, SOL, BNB (свой остаток) → токены своей сети; DOGE → мемы;
  лидер сектора (наибольший оборот в прошлом месяце) → другие члены; корзина сектора без монеты → монета;
  крупные половины сектора → мелкие; обратные направления — для сравнения.
- кросс-корреляция ρ(k) = corr(x_t, y_{t+k}), пулированная по парам «ведущий–ведомый» и месяцам; наклон b = Σxy/Σx²;
  «2σ → ответ» — ожидаемый ответ ведомого на ход ведущего в 2σ (b·2σ_x).
Запуск: из /home/user/mc_data — python3 -I <repo>/research/s275/study/leadlag_design.py → OUT/leadlag_design.txt"""
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common275 import BAR, DESIGN, H, OUT, load_k, panel, perps, sectors, ts, universe  # noqa: E402

PER = "2022–2024"
LINES = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LINES.append(s)


def alt_factor(R, QV, iB, steps_day):
    cs = np.cumsum(QV, axis=1)
    v = np.zeros_like(cs); v[:, steps_day:] = cs[:, steps_day:] - cs[:, :-steps_day]
    ok = np.zeros(R.shape, bool); ok[:, 1:] = v[:, :-1] >= 5e6
    ok[iB] = False
    X = np.where(ok & np.isfinite(R), np.clip(R, -0.5, 0.5), np.nan)
    with np.errstate(all="ignore"):
        return np.nanmean(X, axis=0)


def month_starts():
    out = []
    y, m = 2022, 11
    while (y, m) <= (2023, 10):
        out.append(ts(f"{y}-{m:02d}-01"))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def run(step):
    K = load_k(PER)
    P = perps(K)
    SEC = sectors()
    LR = universe(K, P, PER)
    pidx = {p: k for k, p in enumerate(P)}
    iB = pidx["BTC"]
    t0, t1 = DESIGN
    T, LC, QV = panel(K, P, t0, t1, step)
    R = np.full(LC.shape, np.nan); R[:, 1:] = LC[:, 1:] - LC[:, :-1]
    spd = DAY_STEPS = int(86400 // step)  # noqa: F841
    alt = alt_factor(R, QV, iB, spd)
    btc = R[iB]
    MS = month_starts()
    lags = (0, 1, 2, 4) if step == BAR else (0, 1, 2)
    acc = {}

    def add(key, x, y):
        for k in lags:
            a = x[: len(x) - k] if k else x
            b = y[k:]
            ok = np.isfinite(a) & np.isfinite(b)
            if ok.sum() < 50:
                continue
            s = acc.setdefault((key, k), np.zeros(5))
            s += [np.sum(a[ok] * b[ok]), np.sum(a[ok] ** 2), np.sum(b[ok] ** 2), ok.sum(), 1]

    for mi in range(len(MS) - 1):
        a0, a1 = MS[mi], MS[mi + 1]
        f0 = MS[mi - 1] if mi > 0 else ts("2022-10-01")
        ev = (T > a0) & (T <= a1); fit = (T > f0) & (T <= a0)
        U = [p for p in sorted(LR.get(int(a0 // 86400 * 86400), ())) if p in pidx]
        U = [p for p in U if np.isfinite(R[pidx[p], ev]).mean() >= 0.9 and np.isfinite(R[pidx[p], fit]).mean() >= 0.9]
        liq = {p: QV[pidx[p], fit].sum() for p in U}
        rank = {p: r for r, p in enumerate(sorted(U, key=lambda p: -liq[p]))}
        E = {}
        X = np.column_stack([np.ones(R.shape[1]), btc, alt])
        for p in U:
            i = pidx[p]
            if i == iB:
                continue
            y = R[i]
            ok = fit & np.isfinite(y) & np.isfinite(X).all(1)
            if ok.sum() < 200:
                continue
            b, *_ = np.linalg.lstsq(X[ok], y[ok], rcond=None)
            E[p] = (y - X @ b)[ev]
        bt = btc[ev]
        # BTC → альты (сырые доходы)
        for p in E:
            grp = "топ-30" if rank[p] < 30 else "31–100"
            add(f"BTC (сырой) → альт (сырой), {grp}", bt, R[pidx[p], ev])
            add(f"альт (сырой) → BTC (сырой), {grp}", R[pidx[p], ev], bt)
        # родная монета сети → токены сети
        for lead, eco in (("ETH", "Ethereum"), ("SOL", "Solana"), ("BNB", "BNB Chain")):
            if lead not in E:
                continue
            for p in E:
                if p != lead and SEC.get(p, {}).get("eco") == eco:
                    add(f"{lead} → токены сети {eco}", E[lead], E[p])
                    add(f"токены сети {eco} → {lead}", E[p], E[lead])
        if "DOGE" in E:
            for p in E:
                if p != "DOGE" and SEC.get(p, {}).get("sector") == "Meme":
                    add("DOGE → мемы", E["DOGE"], E[p]); add("мемы → DOGE", E[p], E["DOGE"])
        # лидер сектора → члены; корзина сектора без монеты → монета; крупные → мелкие
        secU = {}
        for p in E:
            s = SEC.get(p, {}).get("sector", "")
            if s:
                secU.setdefault(s, []).append(p)
        for s, mem in secU.items():
            if len(mem) < 4:
                continue
            mem = sorted(mem, key=lambda p: -liq[p])
            lead = mem[0]
            for p in mem[1:]:
                add("лидер сектора → член сектора", E[lead], E[p])
                add("член сектора → лидер сектора", E[p], E[lead])
            Mx = np.array([E[p] for p in mem])
            for j, p in enumerate(mem):
                others = np.delete(Mx, j, axis=0)
                with np.errstate(all="ignore"):
                    bk = np.nanmean(others, axis=0)
                add("корзина сектора (без монеты) → монета", bk, E[p])
                add("монета → корзина сектора (без монеты)", E[p], bk)
            half = len(mem) // 2
            with np.errstate(all="ignore"):
                big = np.nanmean(Mx[:half], axis=0); small = np.nanmean(Mx[half:], axis=0)
            add("крупная половина сектора → мелкая", big, small)
            add("мелкая половина сектора → крупная", small, big)
        # случайные пары (контроль): ведущий — случайная монета другого сектора
        rng = np.random.default_rng(int(a0))
        names = list(E)
        for _ in range(300):
            a_, b_ = rng.choice(len(names), 2, replace=False)
            pa, pb = names[a_], names[b_]
            if SEC.get(pa, {}).get("sector") != SEC.get(pb, {}).get("sector"):
                add("контроль: случайная монета другого сектора → монета", E[pa], E[pb])
    lab = "15 мин" if step == BAR else "1 ч"
    say(f"\n## Опережение-запаздывание, шаг {lab} (лаг k — в шагах; ρ(0) — одновременная)")
    keys = sorted({k for k, _ in acc})
    for key in keys:
        parts = []
        for k in lags:
            s = acc.get((key, k))
            if s is None:
                continue
            rho = s[0] / np.sqrt(s[1] * s[2]); b = s[0] / s[1]; sx = np.sqrt(s[1] / s[3])
            se = 1 / np.sqrt(s[3])
            parts.append(f"k={k}: ρ {rho:+.3f}" + (f", 2σ→{b * 2 * sx:+.3%}" if k > 0 else ""))
        n = acc.get((key, 1), np.zeros(5))[3]
        say(f"  {key}: " + "; ".join(parts) + f"  [наблюдений {n:.0f}, СО ρ ≈ {1 / np.sqrt(max(n, 1)):.3f}]")


if __name__ == "__main__":
    t = time.time()
    say("s275 — опережение-запаздывание на отрезке замысла 01.10.2022–01.10.2023 (k_oos)")
    run(BAR)
    run(H)
    open(f"{OUT}/leadlag_design.txt", "w").write("\n".join(LINES) + "\n")
    print(f"готово за {time.time() - t:.0f} с")
