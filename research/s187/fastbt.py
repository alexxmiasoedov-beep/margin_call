"""s187 — быстрый расчёт многих сделок по одной монете: та же логика, что `s15/common.trade` (вход в закрытии 15-мин
свечи i, стоп по худшей из цены стопа и открытия свечи плюс 0,2%, выход в закрытии свечи i + 4·hold_h, комиссия 0,1%
за круг, фактический фандинг), но для массива входов сразу (без тейка). Плюс хедж индексом альтов s103 и плацебо той же
монеты за 45/90/135 сут. Сверка с common.trade — `python3 fastbt.py check` из папки данных."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s141"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import FEE, BAR, K, funding, live  # noqa: E402

DAY = 86400


def trades(s, I, sl=0.25, hold_h=24, side=-1, chunk=4000):
    """Вектор сделок: I — индексы 15-мин свечей входа. Возвращает (ok, net, stop, bars, t_end) — массивы длины len(I)."""
    a = K[s]; t = a["t"].astype(np.int64); n = int(hold_h * 4)
    I = np.asarray(I, np.int64)
    N = len(I)
    ok = np.zeros(N, bool); net = np.full(N, np.nan); stp = np.zeros(N, bool); bars = np.zeros(N, np.int64)
    t_end = np.zeros(N, np.int64)
    if N == 0:
        return ok, net, stp, bars, t_end
    lo_t, hi_t = live(s)
    v = (I >= 0) & (I + n < len(t))
    Iv = np.where(v, I, 0)
    v &= (t[np.minimum(Iv + n, len(t) - 1)] == t[Iv] + n * BAR) & (t[Iv] >= lo_t) & (t[np.minimum(Iv + n, len(t) - 1)] <= hi_t)
    hi, lo, op, c = (a[x].astype(float) for x in ("h", "l", "o", "c"))
    fr = funding(s)
    ft = fr[:, 0].astype(np.int64) if len(fr) else np.zeros(0, np.int64)
    cs = np.r_[0.0, np.cumsum(fr[:, 1])] if len(fr) else np.zeros(1)
    idx = np.flatnonzero(v)
    W_h = np.lib.stride_tricks.sliding_window_view(hi, n) if len(hi) >= n else None
    W_l = np.lib.stride_tricks.sliding_window_view(lo, n) if len(lo) >= n else None
    for k0 in range(0, len(idx), chunk):
        j = idx[k0:k0 + chunk]
        i = I[j]
        p0 = c[i]
        adv = (W_h if side < 0 else W_l)[i + 1]                    # окна свечей i+1 … i+n
        if sl:
            lvl = p0 * (1 - side * sl)
            cond = (side * (adv - lvl[:, None]) <= 0)
            has = cond.any(axis=1)
            ks = np.where(has, cond.argmax(axis=1), n)
        else:
            has = np.zeros(len(i), bool); ks = np.full(len(i), n)
        px = c[i + n].copy()
        xi = i + n
        if has.any():
            hs = np.flatnonzero(has)
            stop = lvl[hs]; o_k = op[i[hs] + 1 + ks[hs]]
            px[hs] = (np.maximum(stop, o_k) * 1.002) if side < 0 else (np.minimum(stop, o_k) * 0.998)
            xi[hs] = i[hs] + 1 + ks[hs]
        t0 = t[i] + BAR; t1 = t[xi] + BAR
        f = cs[np.searchsorted(ft, t1, "right")] - cs[np.searchsorted(ft, t0, "right")] if len(ft) else np.zeros(len(i))
        price = side * (px / p0 - 1)
        net[j] = price - side * f - FEE
        ok[j] = True; stp[j] = has; bars[j] = xi - i; t_end[j] = t1
    return ok, net, stp, bars, t_end


_IDX = {}


def alt_mv(t_from, t_to):
    """Ход индекса альтов s103 между моментами (секунды, массивы): последняя закрытая 15-мин свеча к моменту."""
    if "T" not in _IDX:
        from flow_test import alt_index  # noqa: E402
        _IDX["T"], _IDX["I"] = alt_index(K)
    T, Ix = _IDX["T"], _IDX["I"]
    a = np.searchsorted(T, np.asarray(t_from) - 900, "right") - 1
    b = np.searchsorted(T, np.asarray(t_to) - 900, "right") - 1
    okk = (a >= 0) & (b >= a) & (b < len(Ix))
    out = np.full(len(a), np.nan)
    out[okk] = Ix[b[okk]] / Ix[a[okk]] - 1
    return out


def placebo(s, I, sl, hold_h, side, days=(45, 90, 135)):
    """Среднее той же сделки у той же монеты за days суток до входа (только существующие)."""
    t = K[s]["t"].astype(np.int64)
    I = np.asarray(I, np.int64)
    acc = np.zeros(len(I)); cnt = np.zeros(len(I))
    for d in days:
        tt = t[I] - d * DAY
        j = np.searchsorted(t, tt)
        good = (j < len(t)) & (t[np.minimum(j, len(t) - 1)] == tt) & (j >= 96)
        jj = np.where(good, j, 0)
        okp, netp, *_ = trades(s, jj, sl, hold_h, side)
        g = good & okp
        acc[g] += netp[g]; cnt[g] += 1
    with np.errstate(invalid="ignore"):
        return np.where(cnt > 0, acc / np.maximum(cnt, 1), np.nan)


def check():
    from common import trade  # noqa: E402
    rng = np.random.default_rng(187)
    syms = [s for s in K if (K[s]["qv"] > 0).sum() > 20000][:40]
    bad = tot = 0
    for s in syms:
        t = K[s]["t"]
        I = rng.integers(200, len(t) - 500, 50)
        for side in (-1, 1):
            for hold in (8, 24, 96):
                ok, net, stp, bars, _ = trades(s, I, 0.25, hold, side)
                for k, i in enumerate(I):
                    x = trade(s, int(i), tp=None, sl=0.25, hold_h=hold, side=side)
                    tot += 1
                    if (x is None) != (not ok[k]) or (x is not None and (abs(x["net"] - net[k]) > 1e-9 or x["bars"] != bars[k])):
                        bad += 1
    print(f"сверка с common.trade: {tot} сделок, расхождений {bad}")


if __name__ == "__main__":
    check()
