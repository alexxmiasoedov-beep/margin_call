"""s272 — зоны поддержки и сопротивления, базы, пробои и ложные пробои (запись — ВЫВОДЫ.md, коммит 6393927).

Запуск по периодам — в папке периода (свечи и фандинг периода через s2/k2y.pkl и s2/fund2y.pkl):
  cd ~/mc_2020 && python3 -I <repo>/research/s272/run.py 2020–2022 [count]
  cd ~/mc_oos  && python3 -I <repo>/research/s272/run.py 2022–2024 [count]
  cd ~/mc_data && python3 -I <repo>/research/s272/run.py 2024–2026 [count]
count — только частоты событий (без доходов). Сводка: cd ~/mc_data && python3 -I <repo>/research/s272/run.py report
Сделки — /home/user/mc_data/s272_<период>.pkl."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
OUT = "/home/user/mc_data"
HOUR, BAR, DAY, WEEK = 3600, 900, 86400, 7 * 86400
LIQ, AGE_H, COOL_H = 5e6, 30 * 24, 24
FEE, SLIP = 0.001, 0.002
SKIP = {"BTC", "ETH", "USDC", "FDUSD", "TUSD", "BTCDOM", "DEFI", "XAUT", "PAXG", "USD1"}


def hourly(a):
    t = a["t"].astype(np.int64)
    s0 = int(np.flatnonzero(t % HOUR == 0)[0])
    n = (len(t) - s0) // 4
    sl = slice(s0, s0 + 4 * n)
    if n < 100 or not np.all(np.diff(t[sl]) == BAR):
        return None
    f = lambda k: a[k][sl].astype(float)  # noqa: E731
    O, Hh, L, C, Q = f("o")[::4], f("h").reshape(n, 4).max(1), f("l").reshape(n, 4).min(1), f("c")[3::4], f("qv").reshape(n, 4).sum(1)
    return dict(T=t[sl][::4], O=O, H=Hh, L=L, C=C, Q=Q, s0=s0)


def atr14(H, L, C):
    tr = np.maximum(H - L, np.maximum(np.abs(H - np.r_[C[0], C[:-1]]), np.abs(L - np.r_[C[0], C[:-1]])))
    cs = np.r_[0.0, np.cumsum(tr)]
    n = len(tr); i = np.arange(n)
    out = np.full(n, np.nan)
    ok = i >= 15
    out[ok] = (cs[i[ok]] - cs[i[ok] - 14]) / 14.0                  # среднее TR часов i−14 … i−1 (без текущего)
    return out


def swings(Hx):
    """Развороты вверх: H[j] > max(H[j−3:j]) и H[j] ≥ max(H[j+1:j+4]); известны после закрытия часа j+3."""
    from numpy.lib.stride_tricks import sliding_window_view as sw
    n = len(Hx)
    if n < 10:
        return np.zeros(0, np.int64)
    w = sw(Hx, 3).max(1)                                  # w[k] = max(Hx[k:k+3])
    j = np.arange(3, n - 3)
    ok = (Hx[j] > w[j - 3]) & (Hx[j] >= w[j + 1])
    return j[ok].astype(np.int64)


def zone_events(O, Hx, Lx, C, atr, upto_ok):
    """Движок зон сопротивления в преобразованных ценах (для поддержки цены берутся со знаком минус).
    Возвращает пробои сильных зон и отбои от них: списки dict."""
    sw = swings(Hx)
    zones = []
    brk, bnc = [], []

    def advance(z, upto):
        a, b = z["scan"] + 1, min(upto, z["last"] + 720)
        if a <= b:
            seg = slice(a, b + 1)
            thr = z["top"] + 0.25 * atr[seg]
            hit = np.flatnonzero(C[seg] > thr)
            end = a + int(hit[0]) if hit.size else b + 1
            if len(z["m"]) >= 3 and end > a:
                r = np.arange(a, end)
                wick = Hx[r] - np.maximum(O[r], C[r]); rng = Hx[r] - Lx[r]
                cond = (Hx[r] >= z["bot"]) & (C[r] < z["bot"]) & (wick >= 0.5 * rng) & (rng > 0) & (C[r - 1] < z["bot"])
                for i in r[cond]:
                    bnc.append(dict(h=int(i), top=z["top"], bot=z["bot"], lvl=z["lvl"], n=len(z["m"]), first=z["m"][0][0]))
            if hit.size:
                if len(z["m"]) >= 3:
                    brk.append(dict(h=int(end), top=z["top"], bot=z["bot"], lvl=z["lvl"], n=len(z["m"]), first=z["m"][0][0]))
                z["alive"] = False
            z["scan"] = b
        if upto - z["last"] > 720:
            z["alive"] = False

    for j in sw:
        cj = j + 3
        if not np.isfinite(atr[cj]):
            continue
        keep = []
        for z in zones:                                    # истёкшие зоны (30 сут без касаний) — дочитать события и убрать
            if z["last"] + 720 < cj:
                advance(z, cj)
            elif z["alive"]:
                keep.append(z)
        zones = keep
        cand = sorted((abs(Hx[j] - z["lvl"]), k) for k, z in enumerate(zones) if abs(Hx[j] - z["lvl"]) <= 0.5 * atr[cj])
        best = None
        for _, k in cand:                                  # ближайшая живая зона: сначала дочитать её до часа cj
            z = zones[k]
            advance(z, cj)
            if z["alive"]:
                best = z
                break
        if best is None:
            zones.append(dict(m=[(int(j), float(Hx[j]))], lvl=float(Hx[j]), top=float(Hx[j]), bot=float(Hx[j]), last=int(j),
                              scan=int(cj), alive=True))
        else:
            best["m"].append((int(j), float(Hx[j])))
            hs = [h for _, h in best["m"]]
            best["lvl"], best["top"], best["bot"], best["last"] = float(np.mean(hs)), max(hs), min(hs), int(j)
    for z in zones:
        if z["alive"]:
            advance(z, len(C) - 1)
    return brk, bnc


def events(s, a):
    """Все события сетапов у монеты: список dict(h, setup, dirn, stop, n, age)."""
    hd = hourly(a)
    if hd is None:
        return []
    O, Hh, L, C, Q = hd["O"], hd["H"], hd["L"], hd["C"], hd["Q"]
    atr = atr14(Hh, L, C)
    live = np.flatnonzero(Q > 0)
    if not len(live):
        return []
    first = live[0]
    cq = np.r_[0.0, np.cumsum(Q)]
    i = np.arange(len(C))
    q24 = np.where(i >= 24, cq[i] - cq[np.maximum(i - 24, 0)], 0.0)       # оборот 24 прошлых часов (без текущего)
    ok = (i - first >= AGE_H) & (q24 >= LIQ) & (Q > 0) & np.isfinite(atr) & (atr > 0)
    out = []
    for side in (1, -1):                                   # 1 — сопротивление (цены как есть), −1 — поддержка (цены со знаком минус)
        Ox, Hx, Lx, Cx = (O, Hh, L, C) if side == 1 else (-O, -L, -Hh, -C)
        brk, bnc = zone_events(Ox, Hx, Lx, Cx, atr, ok)
        for e in brk:
            b = e["h"]
            if b >= len(C) - 3 or not ok[b]:
                continue
            vol_ok = b >= 24 and Q[b] >= 1.5 * Q[b - 24:b].mean()
            if vol_ok:                                     # З1: по пробою, стоп за низом зоны
                out.append(dict(h=b, setup="З1", dirn=side, stop=side * (e["bot"] - 0.25 * atr[b]), n=e["n"], age=b - e["first"]))
            for f in (b + 1, b + 2):                       # З2: ложный пробой — закрытие обратно за уровень зоны
                if Cx[f] < e["lvl"]:
                    ex = Hx[b:f + 1].max()
                    out.append(dict(h=f, setup="З2", dirn=-side, stop=side * (ex + 0.25 * atr[b]), n=e["n"], age=f - e["first"]))
                    break
        for e in bnc:                                      # З3: отбой, стоп за верхом зоны
            h = e["h"]
            if ok[h]:
                out.append(dict(h=h, setup="З3", dirn=-side, stop=side * (e["top"] + 0.25 * atr[h]), n=e["n"], age=h - e["first"]))
    # базы: 16 часов с размахом ≤ 2 ATR (ATR на начало базы)
    n = len(C)
    if n > 40:
        from numpy.lib.stride_tricks import sliding_window_view as sw
        hi16 = np.full(n, np.nan); lo16 = np.full(n, np.nan)
        hi16[16:] = sw(Hh, 16).max(1)[:n - 16]; lo16[16:] = sw(L, 16).min(1)[:n - 16]   # окно i−16 … i−1
        a16 = np.r_[np.full(16, np.nan), atr[:n - 16]]
        base = (hi16 - lo16) <= 2 * a16
        for h in np.flatnonzero(base & ok & np.isfinite(hi16)):
            if h >= n - 3:
                continue
            for d, brk_ok in ((1, C[h] > hi16[h]), (-1, C[h] < lo16[h])):
                if not brk_ok:
                    continue
                mid = (hi16[h] + lo16[h]) / 2
                out.append(dict(h=int(h), setup="Б1", dirn=d, stop=mid, n=16, age=16))
                for f in (h + 1, h + 2):                   # Б2: обратно внутрь базы
                    back = C[f] < hi16[h] if d == 1 else C[f] > lo16[h]
                    if back:
                        ex = Hh[h:f + 1].max() if d == 1 else L[h:f + 1].min()
                        out.append(dict(h=int(f), setup="Б2", dirn=-d, stop=ex + d * 0.25 * atr[h], n=16, age=16))
                        break
    # кулдаун 24 ч на сетап и сторону
    out.sort(key=lambda e: e["h"])
    last, keep = {}, []
    for e in out:
        k = (e["setup"], e["dirn"])
        if e["h"] - last.get(k, -10 ** 9) >= COOL_H:
            keep.append(e); last[k] = e["h"]
    for e in keep:
        e["te"] = int(hd["T"][e["h"]]) + HOUR                   # закрытие часа события
        e["i15"] = hd["s0"] + 4 * e["h"] + 3                    # 15-мин свеча, которой кончается час
    return keep


def sim(a, fr_t, fr_cs, I, dirn, stop, nb, tpR=None):
    """Сделка: вход на закрытии 15-мин свечи I, стоп по цене stop (худшая из стопа и открытия свечи ± 0,2%), тейк tpR·R,
    выход через nb свечей; комиссия и фактический фандинг. → (net, стоп?, время выхода) или None."""
    c, h, l, o, t = a["c"], a["h"], a["l"], a["o"], a["t"]
    if I + nb >= len(c):
        return None
    p0 = float(c[I]); R = (p0 - stop) * dirn
    if not (R > 0) or R / p0 > 0.5:
        return None
    hh = h[I + 1:I + nb + 1].astype(float); ll = l[I + 1:I + nb + 1].astype(float)
    adv = (ll <= stop) if dirn > 0 else (hh >= stop)
    ks = int(np.argmax(adv)) if adv.any() else nb
    kt = nb
    if tpR:
        tp = p0 + dirn * tpR * R
        fav = (hh >= tp) if dirn > 0 else (ll <= tp)
        kt = int(np.argmax(fav)) if fav.any() else nb
    if ks < nb and ks <= kt:
        ok_ = float(o[I + 1 + ks])
        px = (min(stop, ok_) * (1 - SLIP)) if dirn > 0 else (max(stop, ok_) * (1 + SLIP))
        xi, st = I + 1 + ks, True
    elif kt < nb:
        px, xi, st = p0 + dirn * tpR * R, I + 1 + kt, False
    else:
        px, xi, st = float(c[I + nb]), I + nb, False
    t0, t1 = int(t[I]) + BAR, int(t[xi]) + BAR
    f = (fr_cs[np.searchsorted(fr_t, t1, "right")] - fr_cs[np.searchsorted(fr_t, t0, "right")]) if len(fr_t) else 0.0
    return dirn * (px / p0 - 1) - dirn * f - FEE, st, t1


def run(per, count_only=False):
    import fastbt as FB  # noqa: E402  (свечи периода — s2/k2y.pkl в текущей папке)
    import common as CM  # noqa: E402
    rows, cnt = [], {}
    for s, a in FB.K.items():
        if s in SKIP or len(a["t"]) < 3000:
            continue
        ev = events(s, a)
        for e in ev:
            cnt[(e["setup"], e["dirn"])] = cnt.get((e["setup"], e["dirn"]), 0) + 1
        if count_only or not ev:
            continue
        fr = CM.funding(s)
        fr_t = fr[:, 0].astype(np.int64) if len(fr) else np.zeros(0, np.int64)
        fr_cs = np.r_[0.0, np.cumsum(fr[:, 1])] if len(fr) else np.zeros(1)
        t = a["t"].astype(np.int64)
        lo_t, hi_t = CM.live(s)
        for e in ev:
            I, d, st = e["i15"], e["dirn"], e["stop"]
            if not (lo_t <= t[I] and I + 96 < len(t) and t[I + 96] <= hi_t):
                continue
            r8 = sim(a, fr_t, fr_cs, I, d, st, 32)
            if r8 is None:
                continue
            r2 = sim(a, fr_t, fr_cs, I, d, st, 32, tpR=2.0)
            r24 = sim(a, fr_t, fr_cs, I, d, st, 96)
            p0 = float(a["c"][I]); rel = (p0 - st) * d / p0
            pls = []
            for w in (7, 14, 21):                          # плацебо: тот же час w сут раньше, та же сторона и тот же риск
                J = I - w * 96
                if J > 0 and t[J] >= lo_t:
                    pj = float(a["c"][J])
                    rp = sim(a, fr_t, fr_cs, J, d, pj * (1 - d * rel), 32)
                    if rp:
                        pls.append(rp[0])
            alt = FB.alt_mv(np.array([int(t[I]) + BAR]), np.array([r8[2]]))[0]
            rows.append(dict(s=s, te=e["te"], setup=e["setup"], dirn=d, n=e["n"], age=e["age"], rel=rel,
                             net=r8[0], stop=r8[1], hed=r8[0] - d * alt, pl=np.mean(pls) if pls else np.nan,
                             net2R=r2[0] if r2 else np.nan, net24=r24[0] if r24 else np.nan))
    print(per, "события:", {f"{k[0]} {'лонг' if k[1] > 0 else 'шорт'}": v for k, v in sorted(cnt.items())}, flush=True)
    if not count_only:
        R = pd.DataFrame(rows)
        R.to_pickle(f"{OUT}/s272_{per}.pkl")
        print(per, "сделок", len(R), flush=True)


def ct(x, t):
    x = np.asarray(x, float); w = (np.asarray(t, np.int64) // WEEK) * WEEK; ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum(); se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x)


def report():
    MO = {"2020–2022": 23.8, "2022–2024": 23.8, "2024–2026": 24.5}
    R = {p: pd.read_pickle(f"{OUT}/s272_{p}.pkl") for p in MO if os.path.exists(f"{OUT}/s272_{p}.pkl")}
    names = {"З1": "пробой сильной зоны", "З2": "ложный пробой зоны", "З3": "отбой от зоны", "Б1": "выход из базы",
             "Б2": "ложный выход из базы"}
    for st in ("З1", "З2", "З3", "Б1", "Б2"):
        for d in (1, -1):
            print(f"\n### {st} {names[st]} — {'лонг' if d > 0 else 'шорт'}")
            allx = []
            for p, X in R.items():
                x = X[(X.setup == st) & (X.dirn == d)]
                allx.append(x)
                if len(x) < 5:
                    print(f"  {p}: n={len(x)}"); continue
                m, t, n = ct(x.net, x.te); mh, th, _ = ct(x.hed, x.te); md, td, _ = ct(x.net - x.pl, x.te)
                mid = float(np.median(x.te))
                h1, h2 = x[x.te < mid].net.mean(), x[x.te >= mid].net.mean()
                m2, t2, _ = ct(x.net2R, x.te); m24, t24, _ = ct(x.net24, x.te)
                print(f"  {p}: n={n} ({n / MO[p]:.0f} в мес.), 8 ч {m:+.2%} (t {t:+.1f}); половины {h1:+.2%} / {h2:+.2%}; "
                      f"с хеджем {mh:+.2%} (t {th:+.1f}); сверх плацебо {md:+.2%} (t {td:+.1f}); стопов {x.stop.mean():.0%}; "
                      f"риск до стопа медиана {x.rel.median():.1%}; тейк 2R {m2:+.2%} (t {t2:+.1f}); 24 ч {m24:+.2%} (t {t24:+.1f})")
            A = pd.concat(allx)
            if len(A) >= 5:
                m, t, n = ct(A.net, A.te); mh, th, _ = ct(A.hed, A.te)
                print(f"  три периода: {m:+.2%} (t {t:+.1f}, n={n}); с хеджем {mh:+.2%} (t {th:+.1f})")
                if st[0] == "З":
                    for k in (3, 4):
                        y = A[A.n >= k] if k == 4 else A[A.n == 3]
                        if len(y) >= 5:
                            m, t, n = ct(y.net, y.te)
                            print(f"    касаний {'≥ 4' if k == 4 else '3'}: {m:+.2%} (t {t:+.1f}, n={n})")


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report()
    else:
        run(sys.argv[1], count_only=len(sys.argv) > 2 and sys.argv[2] == "count")
