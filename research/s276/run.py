"""s276 — проверка Г1–Г5 изучения s275 по протоколу ВЫВОДЫ.md (коммит 55dcfc8; правила — research/s275/ВЫВОДЫ.md, e9f6347).
Запуск из /home/user/mc_data:
  python3 -I <repo>/research/s276/run.py 2020–2022 | 2022–2024 | 2024–2026   — сделки периода → s276_<период>.pkl
  python3 -I <repo>/research/s276/run.py report                              — сводка и порог
События — та же логика, что research/s275/study/freq.py, freq_pairs.py, freq_eco.py (частоты s275)."""
import os
import pickle
import sys
import time

PER = sys.argv[1]
CFG = {"2020–2022": ("s117/k_2020.pkl", "s117/fund_2020.pkl"), "2022–2024": ("s117/k_oos.pkl", "s117/fund_oos.pkl"),
       "2024–2026": ("s224/k_d.pkl", "s224/fund_d.pkl")}
if PER in CFG:
    os.environ["MC_K"], os.environ["MC_F"] = CFG[PER]
HERE = os.path.dirname(os.path.abspath(__file__))
for d in ("s187", os.path.join("s275", "study")):
    sys.path.insert(0, os.path.join(HERE, "..", d))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

DAY, H, BAR, WEEK = 86400, 3600, 900, 7 * 86400
FEE, SLIP = 0.001, 0.002            # комиссия за круг на единицу номинала ноги; проскальзывание стопа
MONTH = 30.44 * DAY


def ts(s):
    return int(pd.Timestamp(s, tz="UTC").timestamp())


SEG = {"П1": (ts("2020-10-01"), ts("2022-10-01")), "замысел": (ts("2022-10-01"), ts("2023-10-01")),
       "П2": (ts("2023-10-01"), ts("2024-10-01")), "П3": (ts("2024-10-01"), ts("2026-10-19")),
       "свежий": (ts("2026-10-19"), ts("2026-11-20"))}
TEST = ("П1", "П2", "П3")


def seg_of(t):
    for k, (a, b) in SEG.items():
        if a <= t < b:
            return k
    return None


# ---------------------------------------------------------------------------------------------------------------------
def run():
    import fastbt as FB  # noqa: E402  (ставит s15 в путь и грузит свечи MC_K)
    import common as CM  # noqa: E402
    from common275 import DESIGN, PER as P275, cooldown, adf_t, half_life, in_universe, perps, sectors, universe  # noqa
    from freq import alt_factor, rolling_resid, rsum, sigma_daily, oi_series  # noqa: E402,F401
    t_s = time.time()
    K = FB.K
    cfg = P275[PER]
    t0, t1 = cfg["t0"], cfg["tb"] or cfg["t1"]
    P = perps(K)
    pidx = {p: k for k, p in enumerate(P)}
    iB = pidx["BTC"]
    LR = universe(K, P, PER)
    SEC = sectors()
    n = int((t1 - t0) // H)
    T = t0 + H * (np.arange(n) + 1)                                      # конец часа
    LC = np.full((len(P), n), np.nan); KC = np.full((len(P), n), np.nan); QV = np.zeros((len(P), n))
    for k, p in enumerate(P):
        a = K[p]; t = a["t"].astype(np.int64)
        m = (t >= t0) & (t < t1)
        if not m.any():
            continue
        tt = t[m]; c = a["c"][m].astype(float); q = a["qv"][m].astype(float)
        h = (tt - t0) // H
        np.add.at(QV[k], h, q)
        last = ((tt - t0) % H) == H - BAR
        KC[k, h[last & (c > 0)]] = c[last & (c > 0)]
        ok = last & (q > 0) & (c > 0)
        LC[k, h[ok]] = np.log(c[ok])
    R = np.full(LC.shape, np.nan); R[:, 1:] = LC[:, 1:] - LC[:, :-1]
    alt = alt_factor(R, QV, iB); btc = R[iB]
    ALTc = np.r_[0.0, np.cumsum(np.where(np.isfinite(alt), alt, 0.0))][1:]
    # нога «индекс альтов» в сделке — портфель равных весов с ребалансом каждый час (протокол): его доход за час —
    # среднее простых доходов тех же перпов, что в alt_factor; exp(Σ среднего лог-дохода) отстаёт от него
    # на половину поперечной дисперсии за каждый час (так считалось в первом прогоне, сводка v1)
    cq0 = np.cumsum(QV, axis=1); v0 = np.zeros_like(cq0); v0[:, 24:] = cq0[:, 24:] - cq0[:, :-24]
    okA = np.zeros(R.shape, bool); okA[:, 1:] = v0[:, :-1] >= 5e6; okA[iB] = False
    with np.errstate(all="ignore"):
        alt_s = np.nanmean(np.where(okA & np.isfinite(R), np.expm1(np.clip(R, -0.5, 0.5)), np.nan), axis=0)
    ALTl = np.cumprod(1.0 + np.where(np.isfinite(alt_s), alt_s, 0.0))
    del cq0, v0, okA
    print(f"  отставание exp(Σ лог) от портфеля за 24 ч: {np.nanmean(ALTl[24:] / ALTl[:-24] - np.exp(ALTc[24:] - ALTc[:-24])):+.3%}",
          flush=True)
    BTCc = np.r_[0.0, np.cumsum(np.where(np.isfinite(btc), btc, 0.0))][1:]
    cq = np.cumsum(QV, axis=1); v24 = np.zeros_like(cq); v24[:, 24:] = cq[:, 24:] - cq[:, :-24]
    CONS = v24 >= 5e6; CONS[iB] = False                                   # перпы индекса альтов на момент входа
    CF = np.zeros((len(P), n))                                            # накопленный фандинг на конец часа
    FT = {}
    for k, p in enumerate(P):
        f = CM.funding(p)
        if len(f):
            ft = f[:, 0].astype(np.int64); cs = np.r_[0.0, np.cumsum(f[:, 1].astype(float))]
            CF[k] = cs[np.searchsorted(ft, T, "right")]
            FT[p] = (ft, f[:, 1].astype(float))
    M = in_universe(T, P, LR)
    day = ((T - 1) // DAY) * DAY
    print(f"== {PER}: перпов {len(P)}, часов {n}, панель {time.time() - t_s:.0f} с", flush=True)

    # ранг монеты во вселенной суток — по обороту за 720 часов до начала суток (как freq.rank_of)
    RANK = {}
    for d, S in LR.items():
        j = int(np.searchsorted(T, d)) - 1
        if j < 0:
            continue
        lo = max(0, j - 720)
        vals = sorted(((cq[pidx[q], j] - cq[pidx[q], lo], q) for q in S if q in pidx), reverse=True)
        RANK[int(d)] = {q: r for r, (_, q) in enumerate(vals)}

    def rank_of(p, j):
        return RANK.get(int(day[j]), {}).get(p, 999)

    def fund_alt(j0, k):
        m = CONS[:, j0]
        return float(np.mean(CF[m, k] - CF[m, j0])) if m.any() else 0.0

    def hedge(j0, k, b, c):
        return b * (KC[iB, k] / KC[iB, j0] - 1) + c * (ALTl[k] / ALTl[j0] - 1)

    def hedge_fund(j0, k, b, c):
        return b * (CF[iB, k] - CF[iB, j0]) + c * fund_alt(j0, k)

    # коэффициенты остатка (как freq.rolling_resid, но с самими коэффициентами)
    def coefs(y, win=720, min_n=300):
        v = np.isfinite(y) & np.isfinite(btc) & np.isfinite(alt)
        yy = np.where(v, y, 0.0); bb = np.where(v, btc, 0.0); aa = np.where(v, alt, 0.0); vv = v.astype(float)
        cs = {k: np.concatenate([[0.0], np.cumsum(x)]) for k, x in
              dict(n=vv, b=bb, a=aa, y=yy, bb=bb * bb, aa=aa * aa, ab=aa * bb, by=bb * yy, ay=aa * yy).items()}
        C = np.full((3, len(y)), np.nan)
        starts = np.flatnonzero(np.r_[True, day[1:] != day[:-1]]); ends = np.r_[starts[1:], len(T)]
        for s0, s1 in zip(starts, ends):
            lo = max(0, s0 - win)
            S = {k: c[s0] - c[lo] for k, c in cs.items()}
            if S["n"] < min_n:
                continue
            Mx = np.array([[S["n"], S["b"], S["a"]], [S["b"], S["bb"], S["ab"]], [S["a"], S["ab"], S["aa"]]])
            try:
                C[:, s0:s1] = np.linalg.solve(Mx, np.array([S["y"], S["by"], S["ay"]]))[:, None]
            except np.linalg.LinAlgError:
                continue
        e = y - C[0] - C[1] * btc - C[2] * alt
        return C, e

    rows = []

    def put(hyp, var, j0, net, st, pl, s, k_exit):
        te = int(T[j0])
        sg = seg_of(te)
        if sg is not None and np.isfinite(net):
            rows.append(dict(hyp=hyp, var=var, seg=sg, te=te, tx=int(T[k_exit]), net=float(net), stop=bool(st),
                             pl=float(pl) if pl is not None else np.nan, s=s))

    # --- Г1 / Г2: сделка монетой против рынка со стопом по остатку ---------------------------------------------------
    def tr_resid(i, C, sig, j0, side, nh=24, mult=2.0):
        j1 = j0 + nh
        if j0 < 1 or j1 >= n or not np.isfinite(LC[i, j0]) or not np.isfinite(KC[i, j0]):
            return None
        a0, b0, c0 = C[:, j0]
        thr = mult * sig[j0]
        if not (np.isfinite(a0) and np.isfinite(thr) and thr > 0):
            return None
        k_exit, st = j1, False
        for k in range(j0 + 1, j1 + 1):
            if not np.isfinite(LC[i, k]):
                continue
            res = (LC[i, k] - LC[i, j0]) - a0 * (k - j0) - b0 * (BTCc[k] - BTCc[j0]) - c0 * (ALTc[k] - ALTc[j0])
            if side * res <= -thr:
                k_exit, st = k, True
                break
        if not np.isfinite(KC[i, k_exit]):
            return None
        coin = KC[i, k_exit] / KC[i, j0] - 1
        net = (side * coin - side * hedge(j0, k_exit, b0, c0) - FEE * (1 + abs(b0) + abs(c0)) - (SLIP if st else 0.0)
               - side * (CF[i, k_exit] - CF[i, j0]) + side * hedge_fund(j0, k_exit, b0, c0))
        return net, st, k_exit

    E = {}
    for p in P:
        if p == "BTC" or not M[pidx[p]].any():
            continue
        i = pidx[p]
        C, e = coefs(R[i])
        s24 = rsum(e, 24); sig = sigma_daily(s24, T)
        z = s24 / sig
        E[p] = (C, e, sig)
        mem = M[i]
        slots = np.flatnonzero(mem & ((T % (4 * H)) == 0) & np.isfinite(z))
        daily = np.flatnonzero(mem & ((T % DAY) == 0) & np.isfinite(z))

        def go(j_arr):
            return list(j_arr[cooldown(T[j_arr], DAY)]) if len(j_arr) else []

        ev = {("Г1", "основной"): (go(slots[z[slots] <= -2]), -1),
              ("Г1", "порог −3σ"): (go(slots[z[slots] <= -3]), -1),
              ("Г1", "только 00:00 UTC"): (go(daily[z[daily] <= -2]), -1),
              ("Г1", "зеркало: рост ≥ +2σ → лонг"): (go(slots[z[slots] >= 2]), 1),
              ("Г2", "+3σ"): (go(slots[z[slots] >= 3]), -1),
              ("Г2", "порог +2σ (топ-100)"): (go(slots[z[slots] >= 2]), -1)}
        for (hyp, var), (js, side) in ev.items():
            for j0 in js:
                r = tr_resid(i, C, sig, j0, side)
                if r is None:
                    continue
                pl = [tr_resid(i, C, sig, j0 - 24 * w, side) for w in (7, 14, 21)]
                pl = [x[0] for x in pl if x is not None and np.isfinite(x[0])]
                pm = np.mean(pl) if pl else np.nan
                rk = rank_of(p, j0)
                if hyp == "Г1":
                    put("Г1", var, j0, r[0], r[1], pm, p, r[2])
                    if var == "основной":
                        put("Г1", "топ-30" if rk < 30 else "31–100", j0, r[0], r[1], pm, p, r[2])
                elif var == "+3σ":
                    if 30 <= rk < 100:
                        put("Г2", "основной", j0, r[0], r[1], pm, p, r[2])
                        ft = FT.get(p)
                        veto = False
                        if ft is not None:
                            q = np.searchsorted(ft[0], T[j0], "right") - 1
                            if q >= 1:
                                iv = max((ft[0][q] - ft[0][q - 1]) / H, 1.0)
                                veto = ft[1][q] * 8 / iv <= -0.001
                        if not veto:
                            put("Г2", "без фандинга ≤ −0,1% за 8 ч", j0, r[0], r[1], pm, p, r[2])
                else:
                    put("Г2", var, j0, r[0], r[1], pm, p, r[2])
                    if rk < 30:
                        put("Г2", "топ-30, рост ≥ +2σ (контроль)", j0, r[0], r[1], pm, p, r[2])
    print(f"  Г1, Г2: {time.time() - t_s:.0f} с, сделок {len(rows)}", flush=True)

    # --- Г3: лонг (зеркало — шорт) монеты против рынка, стоп по цене монеты на 15-мин свечах ------------------------
    def tr_price(p, i, C, j0, side, nh=4, sl=0.08):
        j1 = j0 + nh
        if j0 < 1 or j1 >= n or not np.isfinite(KC[i, j0]):
            return None
        a0, b0, c0 = C[:, j0]
        if not np.isfinite(b0):
            return None
        a = K[p]
        if p not in TT:
            TT[p] = a["t"].astype(np.int64)
        t = TT[p]
        I0 = int(np.searchsorted(t, T[j0] - BAR))
        if I0 + 4 * nh >= len(t) or t[I0] != T[j0] - BAR or t[I0 + 4 * nh] != T[j0] - BAR + 4 * nh * BAR:
            return None
        p0 = float(a["c"][I0]); stop = p0 * (1 - side * sl)
        seg = slice(I0 + 1, I0 + 1 + 4 * nh)
        adv = (a["l"][seg].astype(float) <= stop) if side > 0 else (a["h"][seg].astype(float) >= stop)
        if adv.any():
            q = int(np.argmax(adv)); o = float(a["o"][I0 + 1 + q])
            px = min(stop, o) * (1 - SLIP) if side > 0 else max(stop, o) * (1 + SLIP)
            k_exit, st = j0 + q // 4 + 1, True
        else:
            px, k_exit, st = float(a["c"][I0 + 4 * nh]), j1, False
        coin = px / p0 - 1
        net = (side * coin - side * hedge(j0, k_exit, b0, c0) - FEE * (1 + abs(b0) + abs(c0))
               - side * (CF[i, k_exit] - CF[i, j0]) + side * hedge_fund(j0, k_exit, b0, c0))
        return net, st, k_exit

    TT = {}
    down = (alt <= -0.01) | (btc <= -0.01); up = (alt >= 0.01) | (btc >= 0.01)
    for p, (C, e, sig) in E.items():
        i = pidx[p]
        oi = oi_series(PER, p, T)
        doi = np.full(n, np.nan)
        if oi is not None:
            with np.errstate(all="ignore"):
                doi[1:] = oi[1:] / oi[:-1] - 1
        base3 = M[i] & down & (e <= -0.02)
        ev = [("основной: OI ≤ −3%", base3 & (doi <= -0.03), 1, 4), ("OI ≤ −5%", base3 & (doi <= -0.05), 1, 4),
              ("без условия OI", base3, 1, 4), ("выход 2 ч", base3 & (doi <= -0.03), 1, 2),
              ("выход 8 ч", base3 & (doi <= -0.03), 1, 8),
              ("зеркало: рынок вверх, выше беты, OI ≤ −5% → шорт", M[i] & up & (e >= 0.02) & (doi <= -0.05), -1, 4)]
        for var, cond, side, nh in ev:
            js = np.flatnonzero(cond)
            if not len(js):
                continue
            for j0 in js[cooldown(T[js], 4 * H)]:
                r = tr_price(p, i, C, j0, side, nh)
                if r is None:
                    continue
                pl = [tr_price(p, i, C, j0 - 24 * w, side, nh) for w in (7, 14, 21)]
                pl = [x[0] for x in pl if x is not None and np.isfinite(x[0])]
                put("Г3", var, j0, r[0], r[1], np.mean(pl) if pl else np.nan, p, r[2])
    print(f"  Г3: {time.time() - t_s:.0f} с, сделок {len(rows)}", flush=True)

    # --- Г4: пары одного сектора (контроль) --------------------------------------------------------------------------
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

    def pair_ret(iy, ix, ny, nx, k0, k1):
        ry = KC[iy, k1] / KC[iy, k0] - 1; rx = KC[ix, k1] / KC[ix, k0] - 1
        fy = CF[iy, k1] - CF[iy, k0]; fx = CF[ix, k1] - CF[ix, k0]
        return ny * ry + nx * rx - ny * fy - nx * fx

    mondays = [d for d in sorted(LR) if (d // DAY + 3) % 7 == 0]
    for d in mondays:
        U = [p for p in sorted(LR[d]) if p in pidx and p != "BTC"]
        j0 = int(np.searchsorted(T, d, "right")) - 1
        if j0 < 720:
            continue
        form = slice(j0 - 719, j0 + 1)
        U = [p for p in U if np.isfinite(LC[pidx[p], form]).mean() >= 0.9]
        groups = {"main": {}, "sub": {}}
        for p in U:
            s = SEC.get(p, {})
            if s.get("sector"):
                groups["main"].setdefault(s["sector"], []).append(p)
            if s.get("subsector"):
                groups["sub"].setdefault(s["subsector"], []).append(p)
        cand = {}
        for g in ("main", "sub"):
            cand[g] = sorted({(m[a], m[b]) for m in groups[g].values() for a in range(len(m)) for b in range(a + 1, len(m))})
        rng = np.random.default_rng(d)
        allp = [(U[a], U[b]) for a in range(len(U)) for b in range(a + 1, len(U))]
        pick = rng.choice(len(allp), min(len(cand["main"]), len(allp)), replace=False) if allp else []
        cand["any"] = sorted({allp[k] for k in pick})
        cache = {}
        for g in ("main", "sub", "any"):
            for pa, pb in cand[g]:
                if (pa, pb) not in cache:
                    la, lb = LC[pidx[pa], form], LC[pidx[pb], form]
                    ok = np.isfinite(la) & np.isfinite(lb)
                    t_, bb, u, sw = eg(la[ok], lb[ok])
                    cache[(pa, pb)] = (t_, bb, u.mean(), u.std(), half_life(u), sw)
                t_, bb, mu, sd, hl, sw = cache[(pa, pb)]
                if not (t_ <= -3.34 and sd >= 0.015):
                    continue
                vars_ = []
                if g == "main":
                    vars_.append("без фильтра полураспада")
                    if hl <= 12:
                        vars_.append("основной")
                elif hl <= 12:
                    vars_.append("подсектор" if g == "sub" else "случайные пары (контроль отбора)")
                if not vars_:
                    continue
                py, px_ = (pb, pa) if sw else (pa, pb)
                iy, ix = pidx[py], pidx[px_]
                kend = min(j0 + 168 + 24, n - 1)
                zz = (LC[iy, j0 + 1:kend + 1] - bb[0] - bb[1] * LC[ix, j0 + 1:kend + 1] - mu) / sd
                ks = np.arange(j0 + 1, kend + 1)
                week_end = j0 + 168
                i_ = 1
                while i_ < len(zz) and ks[i_] <= week_end:
                    if np.isfinite(zz[i_]) and np.isfinite(zz[i_ - 1]) and abs(zz[i_]) >= 2 > abs(zz[i_ - 1]):
                        s_ = np.sign(zz[i_]); k0 = ks[i_]; jx = i_ + 1; st = False
                        while jx < len(zz) and jx - i_ < 24:
                            if np.isfinite(zz[jx]):
                                if abs(zz[jx]) >= 4:
                                    st = True; break
                                if np.sign(zz[jx]) != s_:
                                    break
                            jx += 1
                        jx = min(jx, len(zz) - 1)
                        k1 = ks[jx]
                        ny, nx = -s_, s_ * bb[1]
                        if np.isfinite(KC[iy, k0]) and np.isfinite(KC[iy, k1]) and np.isfinite(KC[ix, k0]) \
                                and np.isfinite(KC[ix, k1]):
                            net = pair_ret(iy, ix, ny, nx, k0, k1) - FEE * (1 + abs(bb[1])) - (SLIP * (1 + abs(bb[1])) if st else 0.0)
                            pls = []
                            for w in (7, 14, 21):
                                a0_, a1_ = k0 - 24 * w, k1 - 24 * w
                                if a0_ >= 1 and all(np.isfinite(KC[q, a]) for q in (iy, ix) for a in (a0_, a1_)):
                                    pls.append(pair_ret(iy, ix, ny, nx, a0_, a1_) - FEE * (1 + abs(bb[1])))
                            for v in vars_:
                                put("Г4", v, int(k0), net, st, np.mean(pls) if pls else np.nan, f"{py}/{px_}", int(k1))
                        i_ = jx + 1
                    else:
                        i_ += 1
    print(f"  Г4: {time.time() - t_s:.0f} с, сделок {len(rows)}", flush=True)

    # --- Г5: догон экосистемы ----------------------------------------------------------------------------------------
    NATIVE = {"SOL": "Solana", "BNB": "BNB Chain", "SUI": "Sui", "TON": "TON", "AVAX": "Avalanche", "TRX": "Tron"}
    from freq_eco import sigma1  # noqa: E402
    S1 = {}
    for p in set(NATIVE) | {q for q in P if SEC.get(q, {}).get("eco") in NATIVE.values()}:
        if p in pidx:
            if p not in E:
                C, e = coefs(R[pidx[p]]); E[p] = (C, e, None)
            S1[p] = sigma1(E[p][1], T)

    def tr_eco(nat, fol, sgn, j0, nh=4, sl=0.05):
        j1 = j0 + nh
        if j0 < 1 or j1 >= n:
            return None
        legs = [(pidx[q], sgn / len(fol)) for q in fol] + [(pidx[nat], -sgn)]
        if not all(np.isfinite(KC[i, j0]) for i, _ in legs):
            return None
        k_exit, st = j1, False
        for k in range(j0 + 1, j1 + 1):
            if not all(np.isfinite(KC[i, k]) for i, _ in legs):
                continue
            v = sum(w * (KC[i, k] / KC[i, j0] - 1) for i, w in legs)
            if v <= -sl and k < j1:
                k_exit, st = k, True
                break
        if not all(np.isfinite(KC[i, k_exit]) for i, _ in legs):
            return None
        net = sum(w * (KC[i, k_exit] / KC[i, j0] - 1) - w * (CF[i, k_exit] - CF[i, j0]) for i, w in legs)
        return net - FEE * 2 - (SLIP * 2 if st else 0.0), st, k_exit

    for nat, chain in NATIVE.items():
        if nat not in E or nat not in S1:
            continue
        e = E[nat][1]; zz = e / S1[nat]
        js = np.flatnonzero(np.isfinite(zz) & (np.abs(zz) >= 2))
        if not len(js):
            continue
        toks = [q for q in E if q != nat and SEC.get(q, {}).get("eco") == chain and q in S1]
        for j0 in js[cooldown(T[js], 4 * H)]:
            sgn = float(np.sign(e[j0]))
            U = LR.get(int(day[j0]), set())
            fol = [q for q in toks if q in U and np.isfinite(E[q][1][j0]) and np.isfinite(S1[q][j0])
                   and E[q][1][j0] * sgn <= 0.5 * S1[q][j0]]
            if not fol:
                continue
            r = tr_eco(nat, fol, sgn, j0)
            if r is None:
                continue
            pl = [tr_eco(nat, fol, sgn, j0 - 24 * w) for w in (7, 14, 21)]
            pl = [x[0] for x in pl if x is not None and np.isfinite(x[0])]
            put("Г5", "основной", j0, r[0], r[1], np.mean(pl) if pl else np.nan, f"{nat}:{len(fol)}", r[2])
    X = pd.DataFrame(rows)
    X.to_pickle(f"s276_{PER}.pkl")
    print(f"  Г5 и всё: {time.time() - t_s:.0f} с; сделок {len(X)}", flush=True)
    print(X.groupby(["hyp", "var", "seg"]).size().to_string(), flush=True)


# ---------------------------------------------------------------------------------------------------------------------
def ct(x, t):
    x = np.asarray(x, float); w = (np.asarray(t, np.int64) // WEEK) * WEEK; ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum(); se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x)


MAINV = {"Г1": "основной", "Г2": "основной", "Г3": "основной: OI ≤ −3%", "Г4": "основной", "Г5": "основной"}


def report():
    X = pd.concat([pd.read_pickle(f"s276_{p}.pkl") for p in CFG if os.path.exists(f"s276_{p}.pkl")], ignore_index=True)
    for hyp in ("Г1", "Г2", "Г3", "Г4", "Г5"):
        H_ = X[X.hyp == hyp]
        vs = sorted(H_["var"].unique(), key=lambda v: (v != MAINV[hyp], v))
        for v in vs:
            x = H_[H_["var"] == v]
            print(f"\n### {hyp} — {v}{'' if v == MAINV[hyp] else ' (для отчёта)'}")
            signs, allx = [], []
            for sg in ("П1", "замысел", "П2", "П3", "свежий"):
                y = x[x.seg == sg]
                if len(y) < 5:
                    if len(y):
                        print(f"  {sg}: n={len(y)}, {y.net.mean():+.2%}")
                    continue
                a0, a1 = SEG[sg]; mo = (a1 - a0) / MONTH
                m, t, nn = ct(y.net, y.te); md, td, _ = ct(y.net - y.pl, y.te)
                mid = float(np.median(y.te)); h1, h2 = y[y.te < mid].net.mean(), y[y.te >= mid].net.mean()
                print(f"  {sg}: n={nn} ({nn / mo:.0f} в мес.), {m:+.2%} (t {t:+.1f}); половины {h1:+.2%} / {h2:+.2%}; "
                      f"сверх плацебо {md:+.2%} (t {td:+.1f}); стопов {y.stop.mean():.0%}; медиана {y.net.median():+.2%}")
                if sg in TEST:
                    signs.append(m > 0); allx.append(y)
                if sg == "П3" and v == MAINV[hyp]:
                    conds = (("≥ 20 в месяц", nn / mo >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                             ("сверх плацебо > 0", md > 0))
                    print("    правило владельца: " + "; ".join(f"{k} — {'да' if c else 'нет'}" for k, c in conds)
                          + f" → {'выполнено' if all(c for _, c in conds) else 'не выполнено'}")
            if allx:
                A = pd.concat(allx); m, t, nn = ct(A.net, A.te)
                ok = all(signs) and t >= 3
                print(f"  вместе ({len(allx)} пер.): {m:+.2%} (t {t:+.1f}, n={nn}); знак плюс во всех — "
                      f"{'да' if all(signs) else 'нет'} → {'ПОРОГ ПРОЙДЕН' if ok else 'не пройден'}")


if __name__ == "__main__":
    report() if PER == "report" else run()
