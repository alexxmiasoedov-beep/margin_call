"""s275 — частота сетапа Г4 (контроль «пары в обычном понимании») на трёх периодах. Доходы не считаются: выход из пары
определяется только для того, чтобы не открывать её повторно, пока она «открыта» (цены пары после входа участвуют
лишь в моменте выхода, результат сделки не считается).

- Отбор пар — каждый понедельник 00:00 UTC: вселенная суток (топ-100 по обороту за 30 сут), пары одного сектора
  (sectors.csv), у обеих монет часовые цены ≥ 90% часов за прошлые 30 сут;
- коинтеграция Энгла–Грейнджера на часовых лог-ценах прошлых 30 сут (направление с меньшей t), ADF t ≤ −3,34;
  полураспад AR(1) спреда ≤ 12 ч; СО спреда σ ≥ 1,5% (2σ ≥ 3% — заметно больше комиссии пары 0,2%);
- неделя торговли: z = (u − μ)/σ по α, β, μ, σ отбора; вход, когда |z| впервые ≥ 2 (до этого < 2) и пара не открыта;
  выход — z пересёк 0, или 24 ч, или |z| ≥ 4 (стоп); ноги — 1 : β по номиналу.
Варианты: без фильтра полураспада; подсектор вместо сектора; любые пары топ-100 (контроль отбора).
Запуск: из /home/user/mc_data — python3 -I <repo>/research/s275/study/freq_pairs.py [период …] → OUT/freq_pairs_<…>.txt"""
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common275 import DAY, H, OUT, PER, adf_t, fmt, freq_line, half_life, load_k, panel, perps, sectors, universe  # noqa

LINES = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LINES.append(s)


def eg(la, lb):
    best = None
    for y_, x_, sw in ((la, lb, False), (lb, la, True)):
        X = np.column_stack([np.ones(len(x_)), x_])
        b, *_ = np.linalg.lstsq(X, y_, rcond=None)
        u = y_ - X @ b
        t = adf_t(u)
        if best is None or t < best[0]:
            best = (t, b, u, sw)
    return best


def entries(z, maxh=24):
    """Входы |z| ≥ 2 после |z| < 2, пока пара не открыта; выход — смена знака z, maxh часов или |z| ≥ 4."""
    out = []
    i, n = 1, len(z)
    while i < n:
        if np.isfinite(z[i]) and np.isfinite(z[i - 1]) and abs(z[i]) >= 2 > abs(z[i - 1]):
            out.append(i)
            s = np.sign(z[i]); j = i + 1
            while j < n and j - i < maxh:
                if not np.isfinite(z[j]):
                    j += 1; continue
                if np.sign(z[j]) != s or abs(z[j]) >= 4:
                    break
                j += 1
            i = j + 1
        else:
            i += 1
    return out


def run(per):
    t_s = time.time()
    cfg = PER[per]
    K = load_k(per)
    P = perps(K)
    SEC = sectors()
    LR = universe(K, P, per)
    pidx = {p: k for k, p in enumerate(P)}
    tend = cfg["tb"] or cfg["t1"]
    T, LC, QV = panel(K, P, cfg["t0"], tend, H)
    del K
    say(f"\n==== {per}: часов {len(T)}")
    mondays = [d for d in sorted(LR) if (d // DAY + 3) % 7 == 0]          # 01.01.1970 — четверг
    variants = {"main": [], "noHL": [], "sub": [], "any": []}
    npairs = {k: [] for k in variants}
    for d in mondays:
        U = [p for p in sorted(LR[d]) if p in pidx and p != "BTC"]
        j0 = int(np.searchsorted(T, d, "right")) - 1                    # последний час, кончившийся не позже d
        if j0 < 720:
            continue
        form = slice(j0 - 719, j0 + 1)
        week = slice(j0 + 1, min(j0 + 1 + 168, len(T)))
        cov = {p: np.isfinite(LC[pidx[p], form]).mean() >= 0.9 for p in U}
        U = [p for p in U if cov[p]]
        groups = {"main": {}, "sub": {}}
        for p in U:
            s = SEC.get(p, {})
            if s.get("sector"):
                groups["main"].setdefault(s["sector"], []).append(p)
            if s.get("subsector"):
                groups["sub"].setdefault(s["subsector"], []).append(p)
        cand = {"main": set(), "sub": set()}
        for g in ("main", "sub"):
            for mem in groups[g].values():
                for a in range(len(mem)):
                    for b in range(a + 1, len(mem)):
                        cand[g].add((mem[a], mem[b]))
        rng = np.random.default_rng(d)
        allpairs = [(U[a], U[b]) for a in range(len(U)) for b in range(a + 1, len(U))]
        pick = rng.choice(len(allpairs), min(len(cand["main"]), len(allpairs)), replace=False) if allpairs else []
        cand["any"] = {allpairs[k] for k in pick}
        cache = {}
        for g, tag in (("main", "main"), ("sub", "sub"), ("any", "any")):
            n_ok = 0
            for pa, pb in cand[g]:
                key = (pa, pb)
                if key not in cache:
                    la, lb = LC[pidx[pa], form], LC[pidx[pb], form]
                    ok = np.isfinite(la) & np.isfinite(lb)
                    t, bb, u, sw = eg(la[ok], lb[ok])
                    cache[key] = (t, bb, u.mean(), u.std(), half_life(u), sw)
                t, bb, mu, sd, hl, sw = cache[key]
                if not (t <= -3.34 and sd >= 0.015):
                    continue
                y = LC[pidx[pb if sw else pa], week]; x = LC[pidx[pa if sw else pb], week]
                z = (y - bb[0] - bb[1] * x - mu) / sd
                ent = entries(z)
                if hl <= 12:
                    n_ok += 1
                    variants[tag].extend(int(T[week][0] + 3600 * k - 3600) for k in ent)
                if tag == "main":
                    variants["noHL"].extend(int(T[week][0] + 3600 * k - 3600) for k in ent)
            npairs[tag].append(n_ok)
    names = dict(main="Г4 пары одного сектора: коинтеграция, HL ≤ 12 ч, σ ≥ 1,5%, вход |z| ≥ 2",
                 noHL="   без фильтра полураспада", sub="   пары одного подсектора (HL ≤ 12 ч)",
                 any="   случайные пары топ-100 (контроль отбора, HL ≤ 12 ч)")
    for k in ("main", "noHL", "sub", "any"):
        say(f"  {names[k]}: {fmt(freq_line(variants[k], per))}")
    say(f"  отобранных пар в неделю (HL ≤ 12 ч): сектор {np.mean(npairs['main']):.1f}, подсектор "
        f"{np.mean(npairs['sub']):.1f}, случайные {np.mean(npairs['any']):.1f} ({time.time() - t_s:.0f} с)")


if __name__ == "__main__":
    pers = sys.argv[1:] or list(PER)
    for per in pers:
        run(per)
    open(f"{OUT}/freq_pairs_{'_'.join(p[:4] for p in pers)}.txt", "w").write("\n".join(LINES) + "\n")
