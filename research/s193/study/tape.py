"""s193 — признаки ленты aggTrades Binance (монета × сутки UTC): следы алгоритмов исполнения.

Только описание ленты: размеры, ритм, сторона, память знака, метки времени, «мытьё», потолки цены. Доходы и цены после
начала эпизода не считаются (правило «гипотезы — до проверки»); из цен хранится только цена в момент обнаружения
и цена первой части эпизода (до обнаружения).

Заявки тейкера восстанавливаются из aggTrades: подряд идущие записи одного времени (мс) и одной стороны = одна заявка
(рыночная заявка, прошедшая несколько уровней цены, даёт несколько aggTrades с одним временем).

Детекторы (математика — в отчёте, раздел 2):
- D1 «одинаковые части»: заявки одной стороны с одним и тем же размером (в монетах); прогоны с паузами ≤ 15 мин;
  регулярность интервалов reg = доля интервалов в ±25% от медианы (у пуассоновского потока ≈ 0,17); чистота стороны —
  доля таких же размеров на другой стороне за время прогона; доля в обороте стороны.
  Обнаружение (без заглядывания вперёд): первая контрольная точка (каждые 10 частей), где частей ≥ 20, прошло ≥ 30 мин,
  reg по прошлым интервалам ≥ 0,5 и чистота ≥ 0,8.
- D1n «одинаковая сумма»: всплеск плотности суммы заявки ($, ячейки 0,2%) ≥ 5× местной плотности; та же проверка прогонов.
- D2 «ритм»: по часам и сторонам — периодограмма счёта крупной половины заявок на сетке 1 с (периоды 4–600 с),
  отношение мощности к местной медиане (SNR).
- D3 «потолок/пол» (заменитель айсберга): 5-мин блоки с одним и тем же максимумом (минимумом) цены подряд; объём покупок
  тейкеров ровно по максимуму (продаж — по минимуму).
- D4 память знака: автокорреляция знака заявок на лагах 1…1000, наклон γ (Lillo–Mike–Farmer), серии одной стороны.
- D5 метки времени: секунда минуты и 50-мс доля секунды.
- D6 Бенфорд по первым цифрам размера и суммы, доля круглых размеров (Cong и др. 2023).
- D7 парные заявки (покупка и продажа одного размера за ≤ 2 с — «мытьё», s14).
- Эталон полноты: синтетические TWAP-вставки (шесть на сутки, разные доля, шаг, длительность, разброс размера и шага)."""
import io
import zipfile

import numpy as np
import pandas as pd
from scipy.ndimage import median_filter

DAYMS = 86_400_000
GMAX = 15 * 60_000            # пауза, рвущая прогон D1
LAGS = np.array([1, 2, 5, 10, 20, 50, 100, 200, 500, 1000])
RLB = np.array([1, 2, 3, 4, 5, 10, 20, 50])           # границы корзин длины серий одной стороны
BENF = np.log10(1 + 1 / np.arange(1, 10))


def read_zip(path):
    """aggTrades → DataFrame a, p, q, T (мс), m (покупатель — мейкер). Заголовок есть не во всех файлах; у спота с 2025 г.
    время в микросекундах."""
    with zipfile.ZipFile(path) as z:
        raw = z.read(z.namelist()[0])
    nl = raw.find(b"\n")
    nf = raw[:nl if nl > 0 else len(raw)].count(b",") + 1
    hdr = 0 if not raw[:1].isdigit() else None
    if hdr == 0:
        df = pd.read_csv(io.BytesIO(raw), header=0, usecols=[0, 1, 2, 5, 6], engine="c")
    else:
        df = pd.read_csv(io.BytesIO(raw), header=None, names=list(range(nf)), usecols=[0, 1, 2, 5, 6],
                         dtype={0: np.int64, 1: np.float64, 2: np.float64, 5: np.int64}, engine="c")
    del raw
    df.columns = ["a", "p", "q", "T", "m"]
    if df.m.dtype != bool:
        df["m"] = df.m.astype(str).str.lower().str.startswith("t")
    t = df["T"].to_numpy(np.int64)
    if len(t) and t[len(t) // 2] > 10 ** 14:
        df["T"] = t // 1000
    if len(df) > 1 and not (np.diff(df.a.to_numpy()) > 0).all():
        df = df.sort_values("a", kind="stable")
    return df


def orders(df):
    """Восстановленные заявки тейкера: t (мс), сторона (+1 покупка, −1 продажа), размер (монет), сумма ($), цена первой
    и последней записи, число уровней цены."""
    t = df["T"].to_numpy(np.int64)
    side = np.where(df.m.to_numpy(bool), -1, 1).astype(np.int8)
    p = df.p.to_numpy(np.float64)
    q = df.q.to_numpy(np.float64)
    n = len(t)
    new = np.empty(n, bool)
    new[0] = True
    new[1:] = (t[1:] != t[:-1]) | (side[1:] != side[:-1])
    st = np.flatnonzero(new)
    en = np.r_[st[1:], n] - 1
    O = dict(t=t[st], s=side[st], q=np.round(np.add.reduceat(q, st), 8), v=np.add.reduceat(p * q, st),
             p0=p[st], p1=p[en], lev=np.diff(np.r_[st, n]).astype(np.int32))
    return O, p, t, side, q


def first_digit(x):
    x = x[x > 0]
    e = np.floor(np.log10(x))
    d = np.floor(x / 10 ** e + 1e-9).astype(int)
    d = np.clip(d, 1, 9)
    return np.bincount(d, minlength=10)[1:]


def is_round(x):
    """1, 2, 2,5, 5 × 10^k (как s91)."""
    x = x[x > 0]
    e = np.floor(np.log10(x))
    m = x / 10 ** e
    return np.isclose(m, 1) | np.isclose(m, 2) | np.isclose(m, 2.5) | np.isclose(m, 5) | np.isclose(m, 10)


def sign_stats(s):
    x = s.astype(np.float64)
    x -= x.mean()
    var = (x * x).mean()
    acf = np.full(len(LAGS), np.nan)
    if var > 0:
        for i, l in enumerate(LAGS):
            if l < len(x) - 10:
                acf[i] = (x[:-l] * x[l:]).mean() / var
    g = np.nan
    ok = (LAGS >= 10) & (acf > 0)
    if ok.sum() >= 4:
        g = -np.polyfit(np.log(LAGS[ok]), np.log(acf[ok]), 1)[0]
    # серии одной стороны
    br = np.flatnonzero(np.r_[True, s[1:] != s[:-1], True])
    rl = np.diff(br)
    rlh = np.histogram(rl, bins=np.r_[RLB, 10 ** 9])[0]
    pst = float((s[1:] == s[:-1]).mean()) if len(s) > 1 else np.nan
    return acf, g, rlh, pst, int(rl.max()) if len(rl) else 0


def _runs_from_times(tr, gmax=GMAX):
    """Границы прогонов в отсортированном массиве времён: пауза > gmax рвёт прогон."""
    br = np.flatnonzero(np.diff(tr) > gmax) + 1
    return np.r_[0, br], np.r_[br, len(tr)]


class Ctx:
    """Кумулятивные суммы оборота по сторонам и времени (для доли эпизода в обороте)."""

    def __init__(self, O):
        self.t = O["t"]
        self.cv = np.r_[0.0, np.cumsum(O["v"])]
        vb = np.where(O["s"] > 0, O["v"], 0.0)
        self.cb = np.r_[0.0, np.cumsum(vb)]
        self.cs = self.cv - self.cb

    def vol(self, t0, t1, side=0):
        i0 = np.searchsorted(self.t, t0, "left")
        i1 = np.searchsorted(self.t, t1, "right")
        c = self.cv if side == 0 else (self.cb if side > 0 else self.cs)
        return c[i1] - c[i0]


def eval_run(tr, vr, pr, side, opp_t, ctx, day0, kind, key):
    """Описание прогона частей одной стороны (времена tr, суммы vr, цены pr) и момент обнаружения без заглядывания."""
    n = len(tr)
    d = np.diff(tr).astype(np.float64)
    med = float(np.median(d))
    reg = float((np.abs(d - med) <= 0.25 * med).mean()) if med > 0 else 0.0
    cv = float(d.std() / d.mean()) if d.mean() > 0 else np.nan
    t0, t1 = int(tr[0]), int(tr[-1])
    nopp = 0
    if opp_t is not None and len(opp_t):
        nopp = int(np.searchsorted(opp_t, t1, "right") - np.searchsorted(opp_t, t0, "left"))
    sv = ctx.vol(t0, t1, side)
    tv = ctx.vol(t0, t1, 0)
    sm = ((tr // 1000) % 60).astype(int)
    smode = float(np.bincount(sm, minlength=60).max() / n)
    row = dict(kind=kind, key=key, side=int(side), n=n, t0=t0, t1=t1, dur=(t1 - t0) / 60000.0, med=med / 1000.0,
               reg=reg, cv=cv, nopp=nopp, pur=n / (n + nopp), vchild=float(np.median(vr)), vtot=float(vr.sum()),
               sh_side=float(vr.sum() / sv) if sv > 0 else np.nan, sh_tot=float(vr.sum() / tv) if tv > 0 else np.nan,
               smode=smode, edge=int((t0 - day0) < GMAX or (day0 + DAYMS - t1) < GMAX), p_first=float(pr[0]),
               det_t=np.nan, n_det=0, med_det=np.nan, reg_det=np.nan, sh_det=np.nan, p_det=np.nan)
    # обнаружение: контрольные точки каждые 10 частей
    j = 19
    while j < n:
        if tr[j] - t0 >= 30 * 60_000:
            dj = d[:j]
            mj = float(np.median(dj))
            rj = float((np.abs(dj - mj) <= 0.25 * mj).mean()) if mj > 0 else 0.0
            no = 0
            if opp_t is not None and len(opp_t):
                no = int(np.searchsorted(opp_t, tr[j], "right") - np.searchsorted(opp_t, t0, "left"))
            if rj >= 0.5 and (j + 1) / (j + 1 + no) >= 0.8:
                svj = ctx.vol(t0, int(tr[j]), side)
                row.update(det_t=int(tr[j]), n_det=j + 1, med_det=mj / 1000.0, reg_det=rj,
                           sh_det=float(vr[:j + 1].sum() / svj) if svj > 0 else np.nan, p_det=float(pr[j]))
                break
        j += 10
    return row


def d1_exact(O, ctx, day0, nmin=10):
    """D1: одинаковые размеры одной стороны."""
    s, q, t, v, p = O["s"], O["q"], O["t"], O["v"], O["p0"]
    idx = np.lexsort((t, q, s))
    S, Q, Tm, V, P = s[idx], q[idx], t[idx], v[idx], p[idx]
    brk = np.r_[True, (S[1:] != S[:-1]) | (Q[1:] != Q[:-1])]
    gs = np.flatnonzero(brk)
    ge = np.r_[gs[1:], len(idx)]
    cnt = ge - gs
    groups = {}
    for a, b in zip(gs, ge):
        groups[(int(S[a]), float(Q[a]))] = (a, b)
    rows = []
    stats = dict(ngroups10=int((cnt >= 10).sum()), top_cnt=int(cnt.max()) if len(cnt) else 0)
    for g in np.flatnonzero(cnt >= nmin):
        a, b = gs[g], ge[g]
        side, qq = int(S[a]), float(Q[a])
        tr_all = Tm[a:b]
        opp = groups.get((-side, qq))
        opp_t = Tm[opp[0]:opp[1]] if opp else None
        rs, re_ = _runs_from_times(tr_all)
        for x, y in zip(rs, re_):
            if y - x < nmin:
                continue
            rows.append(eval_run(tr_all[x:y], V[a + x:a + y], P[a + x:a + y], side, opp_t, ctx, day0, "Q", qq))
    return rows, stats


def d1_notional(O, ctx, day0, nmin=20, width=0.002, spike=5.0):
    """D1n: всплески плотности суммы заявки ($) одной стороны."""
    rows = []
    nsp = 0
    for side in (1, -1):
        m = (O["s"] == side) & (O["v"] > 1.0)
        if m.sum() < 200:
            continue
        tt, vv, pp = O["t"][m], O["v"][m], O["p0"][m]
        b = np.floor(np.log(vv) / width).astype(np.int64)
        b0 = b.min()
        h = np.bincount(b - b0)
        if len(h) < 40:
            continue
        loc = median_filter(h.astype(np.float64), size=41, mode="nearest")
        sp = np.flatnonzero((h >= nmin) & (h >= spike * np.maximum(loc, 1.0)))
        if not len(sp):
            continue
        nsp += len(sp)
        # слить соседние ячейки всплесков
        used = np.zeros(len(h), bool)
        for k in sp:
            if used[k]:
                continue
            lo, hi = max(k - 1, 0), min(k + 1, len(h) - 1)
            used[lo:hi + 1] = True
            sel = (b - b0 >= lo) & (b - b0 <= hi)
            tr = tt[sel]
            vr = vv[sel]
            pr = pp[sel]
            rs, re_ = _runs_from_times(tr)
            for x, y in zip(rs, re_):
                if y - x < nmin:
                    continue
                key = float(np.exp((k + b0 + 0.5) * width))
                rows.append(eval_run(tr[x:y], vr[x:y], pr[x:y], side, None, ctx, day0, "N", key))
    return rows, dict(nspike=nsp)


def _snr(x):
    """Отношение мощности периодограммы к фону: фон — медианы мощности в 40 полосах, равных в логарифме частоты,
    интерполяция в логарифмах (у белого шума SNR ~ Exp(1)/ln 2)."""
    x = x - x.mean()
    pw = np.abs(np.fft.rfft(x)) ** 2
    k = np.arange(len(pw))
    edges = np.unique(np.round(np.geomspace(2, len(pw) - 1, 41)).astype(int))
    cen, med = [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        if hi - lo >= 3:
            cen.append(np.sqrt(lo * hi))
            med.append(np.median(pw[lo:hi]))
    base = np.exp(np.interp(np.log(np.maximum(k, 1)), np.log(cen), np.log(np.maximum(med, 1e-12))))
    return pw / base


def _hour_counts(O, day0):
    hr = ((O["t"] - day0) // 3_600_000).astype(int)
    sec = ((O["t"] - day0) // 1000 % 3600).astype(int)
    return hr, sec


def d2_period(O, day0, kmin=12, kmax=1800):
    """D2: по часам и сторонам — периодограмма счёта заявок крупной половины на сетке 1 с (периоды 2–300 с). Массив
    (24, 2, 5): период лучшего пика (с), SNR, SNR второй гармоники, SNR той же частоты на другой стороне, число заявок."""
    out = np.full((24, 2, 5), np.nan, np.float32)
    hr, sec = _hour_counts(O, day0)
    for h in range(24):
        mh = hr == h
        if mh.sum() < 50:
            continue
        P = {}
        for si, side in enumerate((1, -1)):
            m = mh & (O["s"] == side)
            if m.sum() < 30:
                P[si] = None
                continue
            v = O["v"][m]
            big = v >= np.median(v)
            x = np.bincount(sec[m][big], minlength=3600).astype(np.float64)
            P[si] = (_snr(x), int(big.sum()))
        for si in (0, 1):
            if P.get(si) is None:
                continue
            snr, nb = P[si]
            k = kmin + int(np.argmax(snr[kmin:kmax + 1]))
            h2 = snr[2 * k] if 2 * k < len(snr) else np.nan
            oth = P.get(1 - si)
            out[h, si] = (3600.0 / k, snr[k], h2, oth[0][k] if oth is not None else np.nan, nb)
    return out


def d2_at(O, day0, side, period, hours):
    """Наибольший SNR периодограммы для стороны на заданном шаге (±1 частотный отсчёт) в заданные часы."""
    k = int(round(3600.0 / period))
    best = 0.0
    hr, sec = _hour_counts(O, day0)
    for h in hours:
        m = (hr == h) & (O["s"] == side)
        if m.sum() < 30:
            continue
        v = O["v"][m]
        big = v >= np.median(v)
        x = np.bincount(sec[m][big], minlength=3600).astype(np.float64)
        r = _snr(x)
        best = max(best, float(np.max(r[max(k - 1, 1):k + 2])))
    return best


def d3_levels(p, t, side, qv, day0, mint=3, minspan=6):
    """D3 (заменитель айсберга): «потолок» — максимум 5-мин блока P, который потом не превышается, а цена возвращается
    ровно к P ещё в ≥ 2 блоках (≥ 3 касания); объём покупок тейкеров ровно по P. «Пол» — то же для минимума и продаж.
    Обнаружение — конец блока третьего касания; объём и доля — до обнаружения."""
    blk = np.clip(((t - day0) // 300_000).astype(int), 0, 287)
    nb = 288
    H = np.full(nb, -np.inf)
    L = np.full(nb, np.inf)
    np.maximum.at(H, blk, p)
    np.minimum.at(L, blk, p)
    pv = p * qv
    V = np.bincount(blk, weights=pv, minlength=nb)
    up = np.unique(p)
    tick = float(np.min(np.diff(up))) if len(up) > 1 else np.nan
    live = np.isfinite(H)
    rows = []
    for kind in ("ceil", "floor"):
        X = H if kind == "ceil" else L
        for b in range(nb):
            if not live[b] or (b > 0 and live[b - 1] and X[b - 1] == X[b]):
                continue
            P = X[b]
            e = b + 1
            touch = [b]
            while e < nb and (not live[e] or (X[e] <= P if kind == "ceil" else X[e] >= P)):
                if live[e] and X[e] == P and e - touch[-1] >= 2:
                    touch.append(e)
                e += 1
            if len(touch) < mint or e - b < minspan:
                continue
            bd = touch[mint - 1]
            m = (blk >= b) & (blk <= bd) & (p == P) & ((side > 0) if kind == "ceil" else (side < 0))
            vl = float(pv[m].sum())
            vt = float(V[b:bd + 1].sum())
            rows.append(dict(kind=kind, b0=b, b_det=bd, span=e - b, touches=len(touch), lvl=float(P), vlev=vl,
                             vtot=vt, nlev=int(m.sum()),
                             rng_ticks=float(np.median((H[b:bd + 1] - L[b:bd + 1])[live[b:bd + 1]] / tick))
                             if tick > 0 else np.nan))
    return rows, tick


def lot_decimals(q):
    x = q[:20000]
    for k in range(0, 9):
        if np.allclose(np.round(x * 10 ** k), x * 10 ** k, atol=1e-6):
            return k
    return 8


def inject(O, day0, rng):
    """Шесть синтетических TWAP в непересекающихся 4-часовых окнах суток; параметры случайны. Возвращает новые массивы
    заявок и описания вставок."""
    dec = lot_decimals(O["q"])
    ctx = Ctx(O)
    add = {k: [] for k in ("t", "s", "q", "v", "p0")}
    meta = []
    for slot in range(6):
        Y = float(rng.choice([0.005, 0.01, 0.02, 0.05, 0.10]))
        P = float(rng.choice([10, 30, 60, 120, 300]))
        dur_h = float(rng.choice([1, 3]))
        mode = str(rng.choice(["exact", "rand10"]))
        jit = float(rng.choice([0.0, 0.2]))
        side = int(rng.choice([1, -1]))
        s0 = day0 + slot * 4 * 3_600_000
        start = s0 + int(rng.uniform(0, (4 - dur_h) * 3_600_000))
        end = start + int(dur_h * 3_600_000)
        sv = ctx.vol(start, end, side)
        nchild = int(dur_h * 3600 / P)
        if sv <= 0 or nchild < 5:
            continue
        child = Y * sv / nchild
        ts = start + (np.arange(nchild) * P * 1000).astype(np.int64)
        if jit > 0:
            ts = ts + (rng.uniform(-jit, jit, nchild) * P * 1000).astype(np.int64)
        i = np.clip(np.searchsorted(O["t"], ts) - 1, 0, len(O["t"]) - 1)
        px = O["p1"][i]
        q0 = np.round(child / px[0], dec)
        if q0 <= 0:
            continue
        if mode == "exact":
            qs = np.full(nchild, q0)
        else:
            qs = np.round(q0 * rng.uniform(0.9, 1.1, nchild), dec)
        qs = np.maximum(qs, 10.0 ** -dec)
        add["t"].append(ts)
        add["s"].append(np.full(nchild, side, np.int8))
        add["q"].append(qs)
        add["v"].append(qs * px)
        add["p0"].append(px)
        meta.append(dict(slot=slot, Y=Y, P=P, dur_h=dur_h, mode=mode, jit=jit, side=side, start=start, end=end,
                         nchild=nchild, q0=float(q0), vchild=float(child)))
    if not meta:
        return None, []
    T2 = np.r_[O["t"], np.concatenate(add["t"])]
    o = np.argsort(T2, kind="stable")
    O2 = dict(t=T2[o], s=np.r_[O["s"], np.concatenate(add["s"])][o], q=np.r_[O["q"], np.concatenate(add["q"])][o],
              v=np.r_[O["v"], np.concatenate(add["v"])][o], p0=np.r_[O["p0"], np.concatenate(add["p0"])][o])
    O2["p1"] = O2["p0"]
    return O2, meta


def match_inj(meta, runsQ, runsN, O2, day0):
    """Для каждой вставки — нашёл ли её D1 (тот же размер и сторона), D1n (сумма ±15%, сторона, перекрытие ≥ 50%)
    и SNR периодограммы на её шаге."""
    out = []
    for m in meta:
        r = dict(m)
        best = None
        for row in runsQ:
            if row["side"] != m["side"] or row["key"] != m["q0"]:
                continue
            ov = min(row["t1"], m["end"]) - max(row["t0"], m["start"])
            if ov > 0.5 * (m["end"] - m["start"]):
                if best is None or row["n"] > best["n"]:
                    best = row
        r.update(q_found=int(best is not None), q_det=int(best is not None and np.isfinite(best["det_t"])),
                 q_reg=best["reg"] if best else np.nan, q_lag=(best["det_t"] - m["start"]) / 60000.0
                 if best is not None and np.isfinite(best["det_t"]) else np.nan)
        bestn = None
        for row in runsN:
            if row["side"] != m["side"] or abs(row["vchild"] / m["vchild"] - 1) > 0.15:
                continue
            ov = min(row["t1"], m["end"]) - max(row["t0"], m["start"])
            if ov > 0.5 * (m["end"] - m["start"]):
                if bestn is None or row["n"] > bestn["n"]:
                    bestn = row
        r.update(n_found=int(bestn is not None), n_det=int(bestn is not None and np.isfinite(bestn["det_t"])))
        hours = sorted(set(range(int((m["start"] - day0) // 3_600_000), int((m["end"] - day0) // 3_600_000) + 1)) &
                       set(range(24)))
        full = [h for h in hours if day0 + h * 3_600_000 >= m["start"] - 600_000 and
                day0 + (h + 1) * 3_600_000 <= m["end"] + 600_000]
        r["p_snr"] = d2_at(O2, day0, m["side"], m["P"], full or hours)
        out.append(r)
    return out


def features(path, mkt, sym, day, inj=0, seed=0):
    """Все признаки суток. day — начало суток UTC (сек)."""
    df = read_zip(path)
    if len(df) < 500:
        return dict(ok=0, n_agg=len(df))
    day0 = int(day) * 1000
    df = df[(df["T"] >= day0) & (df["T"] < day0 + DAYMS)]
    O, p, t, side, qv = orders(df)
    n = len(O["t"])
    ctx = Ctx(O)
    res = dict(ok=1, mkt=mkt, s=sym, d=int(day), n_agg=len(df), n_ord=n, vol=float(O["v"].sum()),
               volb=float(O["v"][O["s"] > 0].sum()), p_open=float(p[0]))
    acf, g, rlh, pst, rlmax = sign_stats(O["s"])
    res.update(acf=acf.astype(np.float32), gamma=g, rlh=rlh.astype(np.int32), p_stay=pst, rl_max=rlmax)
    res["benf_q"] = first_digit(O["q"]).astype(np.int32)
    res["benf_v"] = first_digit(O["v"]).astype(np.int32)
    res["round_q"] = float(is_round(O["q"]).mean())
    vv = O["v"][O["v"] >= 10]
    res["round_v"] = np.nan
    # круглая сумма в пределах 0,1% (как s91)
    if len(vv):
        e = 10 ** np.floor(np.log10(vv))
        mm = vv / e
        rv = np.zeros(len(vv), bool)
        for c in (1, 2, 2.5, 5, 10):
            rv |= np.abs(mm / c - 1) <= 0.001
        res["round_v"] = float(rv.mean())
    sec = ((O["t"] // 1000) % 60).astype(int)
    res["sec_hist"] = np.bincount(sec, minlength=60).astype(np.int32)
    res["ms_hist"] = np.bincount(((O["t"] % 1000) // 50).astype(int), minlength=20).astype(np.int32)
    hr = np.clip(((O["t"] - day0) // 3_600_000).astype(int), 0, 23)
    res["h_vol"] = np.bincount(hr, weights=O["v"], minlength=24).astype(np.float32)
    res["h_volb"] = np.bincount(hr, weights=np.where(O["s"] > 0, O["v"], 0), minlength=24).astype(np.float32)
    res["h_n"] = np.bincount(hr, minlength=24).astype(np.int32)
    res["h_nb"] = np.bincount(hr, weights=(O["s"] > 0).astype(float), minlength=24).astype(np.int32)
    res["vq"] = np.quantile(O["v"], [0.5, 0.9, 0.99]).astype(np.float32)
    res["lev_mean"] = float(O["lev"].mean())
    # D7: парные заявки одного размера разных сторон за ≤ 2 с
    idx = np.lexsort((O["t"], O["q"]))
    qs, ts_, ss = O["q"][idx], O["t"][idx], O["s"][idx]
    pr = (qs[1:] == qs[:-1]) & (ts_[1:] - ts_[:-1] <= 2000) & (ss[1:] != ss[:-1])
    mk = np.zeros(n, bool)
    mk[1:] |= pr
    mk[:-1] |= pr
    res["pair_n"] = float(mk.mean())
    res["pair_v"] = float(O["v"][idx][mk].sum() / max(O["v"].sum(), 1e-9))
    # D1, D1n
    rq, st = d1_exact(O, ctx, day0)
    rn, st2 = d1_notional(O, ctx, day0)
    res.update(st)
    res.update(st2)
    allr = rq + rn
    res["n_runs"] = len(allr)
    res["runs"] = [r for r in allr if np.isfinite(r["det_t"]) or (r["n"] >= 15 and r["reg"] >= 0.35)]
    # D2
    res["d2"] = d2_period(O, day0)
    # D3
    res["lev_runs"], res["tick"] = d3_levels(p, t, side, qv, day0)
    # эталон полноты
    if inj:
        rng = np.random.default_rng(seed)
        O2, meta = inject(O, day0, rng)
        if O2 is not None:
            ctx2 = Ctx(O2)
            rq2, _ = d1_exact(O2, ctx2, day0)
            rn2, _ = d1_notional(O2, ctx2, day0)
            res["inj"] = match_inj(meta, rq2, rn2, O2, day0)
    return res
