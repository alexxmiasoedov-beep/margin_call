"""s275 — частота сетапа Г5 «догон экосистемы»: собственный рывок монеты сети (SOL, BNB, SUI, TON, AVAX, TRX) → токены той же
сети из топ-100, которые за этот час не сдвинулись. Доходы не считаются.

- остаток e = r − a − b·BTC − c·альты (коэффициенты на начало суток по 720 прошлым часам, как freq.py);
- рывок родной монеты: остаток часа |e| ≥ 2σ₁ (σ₁ — СО часового остатка за прошлые 30 сут), не чаще раза в 4 ч;
- ведомые: токены с сетью = сети монеты (sectors.csv, поле eco; без самой монеты), во вселенной суток (топ-100),
  остаток часа в сторону рывка ≤ +0,5σ₁ своего ряда (ещё не сдвинулись);
- сделка (для частоты): ведомые в сторону рывка против родной монеты, 4 ч. Считаются часы-события и ноги (токены).
Запуск: из /home/user/mc_data — python3 -I <repo>/research/s275/study/freq_eco.py → OUT/freq_eco.txt"""
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common275 import DAY, DESIGN, H, OUT, PER, cooldown, fmt, freq_line, load_k, panel, perps, sectors, universe  # noqa: E402
from freq import alt_factor, rolling_resid  # noqa: E402

NATIVE = {"SOL": "Solana", "BNB": "BNB Chain", "SUI": "Sui", "TON": "TON", "AVAX": "Avalanche", "TRX": "Tron"}
LINES = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LINES.append(s)


def sigma1(e, T, win_days=30):
    sig = np.full(len(T), np.nan)
    day = ((T - 1) // DAY) * DAY
    for d in np.unique(day):
        m = (T <= d) & (T > d - win_days * DAY) & np.isfinite(e)
        if m.sum() >= 300:
            sig[day == d] = np.std(e[m])
    return sig


def run(per):
    t_s = time.time()
    cfg = PER[per]
    K = load_k(per)
    P = perps(K)
    SEC = sectors()
    LR = universe(K, P, per)
    pidx = {p: k for k, p in enumerate(P)}
    iB = pidx["BTC"]
    T, LC, QV = panel(K, P, cfg["t0"], cfg["tb"] or cfg["t1"], H)
    del K
    R = np.full(LC.shape, np.nan); R[:, 1:] = LC[:, 1:] - LC[:, :-1]
    alt = alt_factor(R, QV, iB); btc = R[iB]
    day = ((T - 1) // DAY) * DAY
    E = {}; S = {}
    need = set(NATIVE) | {p for p in P if SEC.get(p, {}).get("eco") in NATIVE.values()}
    for p in need:
        if p not in pidx:
            continue
        e = rolling_resid(R[pidx[p]], btc, alt, T)
        E[p] = e; S[p] = sigma1(e, T)
    hours, legs, design = [], [], []
    per_chain = {}
    for nat, chain in NATIVE.items():
        if nat not in E:
            continue
        e, s = E[nat], S[nat]
        z = e / s
        j = np.flatnonzero(np.isfinite(z) & (np.abs(z) >= 2))
        j = j[cooldown(T[j], 4 * H)] if len(j) else j
        toks = [p for p in E if p != nat and SEC.get(p, {}).get("eco") == chain]
        for jj in j:
            sgn = np.sign(e[jj])
            U = LR.get(int(day[jj]), set())
            fol = [p for p in toks if p in U and np.isfinite(E[p][jj]) and np.isfinite(S[p][jj])
                   and E[p][jj] * sgn <= 0.5 * S[p][jj]]
            if fol:
                hours.append(int(T[jj])); legs.extend([int(T[jj])] * len(fol))
                per_chain[nat] = per_chain.get(nat, 0) + 1
                if DESIGN[0] < T[jj] <= DESIGN[1]:          # замысел: только отрезок 10.2022–09.2023
                    for p in fol:
                        f4 = E[p][jj + 1:jj + 5]; n4 = e[jj + 1:jj + 5]
                        if len(f4) == 4 and np.isfinite(f4).all() and np.isfinite(n4).all():
                            design.append((sgn * f4.sum(), sgn * n4.sum()))
    say(f"\n==== {per}")
    say(f"  Г5 часы-события (рывок родной монеты ≥ 2σ, есть ведомые): {fmt(freq_line(hours, per))}")
    say(f"     ноги (ведомые токены): {fmt(freq_line(legs, per))}")
    if design:
        d = np.array(design)
        say(f"     замысел 10.2022–09.2023: ног {len(d)}; остаток ведомого за следующие 4 ч в сторону рывка: среднее "
            f"{d[:, 0].mean():+.2%}, медиана {np.median(d[:, 0]):+.2%}; родной монеты {d[:, 1].mean():+.2%}; "
            f"спред «ведомый − родная» {np.mean(d[:, 0] - d[:, 1]):+.2%}")
    say("     по монетам: " + ", ".join(f"{k} {v}" for k, v in sorted(per_chain.items(), key=lambda x: -x[1])) +
        f" ({time.time() - t_s:.0f} с)")


if __name__ == "__main__":
    for per in sys.argv[1:] or list(PER):
        run(per)
    open(f"{OUT}/freq_eco.txt", "w").write("\n".join(LINES) + "\n")
