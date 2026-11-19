"""s187 — функции Pine Script на массивах numpy (поведение ta.* TradingView), только по прошлым и текущему бару.

Соглашения:
- вход — массивы float64 одной длины, бар i — закрытая свеча i; na Pine — NaN;
- ema/rma начинают со средней SMA первых n значений (как TA-Lib и pine_rma из справки; у встроенной ta.ema возможна
  другая затравка — расхождение затухает за ~5·n баров);
- pivothigh/pivotlow возвращают значение на баре ПОДТВЕРЖДЕНИЯ (центр + right), как Pine: сигнал по пивоту виден
  только через right баров;
- crossover(a, b): a > b и a[1] <= b[1]; при na — ложь.
Если установлен numba (`/home/user/mc_data/s187/venv`), циклы компилируются; без него — тот же код на чистом Python."""
import numpy as np

try:
    from numba import njit
except ImportError:                                   # без numba — обычный Python (медленнее, результат тот же)
    def njit(*a, **k):
        if a and callable(a[0]):
            return a[0]
        return lambda f: f

_sw = np.lib.stride_tricks.sliding_window_view


def f64(x):
    return np.asarray(x, dtype=np.float64)


def nz(x, v=0.0):
    x = f64(x)
    return np.where(np.isnan(x), v, x)


def shift(x, k=1):
    """x[k] Pine: значение k баров назад (NaN в начале)."""
    x = f64(x)
    out = np.full(len(x), np.nan)
    if k == 0:
        return x.copy()
    if k < len(x):
        out[k:] = x[:-k]
    return out


def change(x, k=1):
    return f64(x) - shift(x, k)


def _rolling(x, n, fn):
    x = f64(x)
    out = np.full(len(x), np.nan)
    n = int(n)
    if n <= 0 or len(x) < n:
        return out
    out[n - 1:] = fn(_sw(x, n), axis=1)
    return out


def sma(x, n):
    return _rolling(x, n, np.mean)


def ssum(x, n):
    return _rolling(x, n, np.sum)


def highest(x, n):
    return _rolling(x, n, np.max)


def lowest(x, n):
    return _rolling(x, n, np.min)


def stdev(x, n):
    """ta.stdev — смещённое (по генеральной совокупности)."""
    return _rolling(x, n, np.std)


def dev(x, n):
    """ta.dev — среднее абсолютное отклонение от SMA."""
    x = f64(x)
    out = np.full(len(x), np.nan)
    n = int(n)
    if len(x) < n:
        return out
    W = _sw(x, n)
    out[n - 1:] = np.abs(W - W.mean(axis=1, keepdims=True)).mean(axis=1)
    return out


def wma(x, n):
    x = f64(x)
    n = int(n)
    out = np.full(len(x), np.nan)
    if n <= 0 or len(x) < n:
        return out
    w = np.arange(1, n + 1, dtype=np.float64)
    out[n - 1:] = _sw(x, n) @ w / w.sum()
    return out


def hma(x, n):
    """HMA как в Hull Suite (Pine v4): wma(2·wma(x, n/2) − wma(x, n), round(sqrt(n))); n/2 — целочисленно."""
    n = int(n)
    return wma(2 * wma(x, n // 2) - wma(x, n), int(np.floor(np.sqrt(n) + 0.5)))


def vwma(x, v, n):
    return sma(f64(x) * f64(v), n) / sma(v, n)


def linreg(x, n, offset=0):
    """ta.linreg: значение МНК-прямой по n последним барам в точке n − 1 − offset."""
    x = f64(x)
    n = int(n)
    out = np.full(len(x), np.nan)
    if len(x) < n:
        return out
    W = _sw(x, n)
    k = np.arange(n, dtype=np.float64)
    sx, sxx = k.sum(), (k * k).sum()
    sy = W.sum(axis=1)
    sxy = W @ k
    slope = (n * sxy - sx * sy) / (n * sxx - sx * sx)
    icpt = (sy - slope * sx) / n
    out[n - 1:] = icpt + slope * (n - 1 - offset)
    return out


@njit(cache=True)
def _ewm(x, alpha, n):
    """Рекурсия y = α·x + (1 − α)·y[1] с затравкой SMA первых n подряд идущих не-NaN; NaN в середине — сброс."""
    out = np.full(x.size, np.nan)
    have = False
    y = 0.0
    run = 0
    acc = 0.0
    for i in range(x.size):
        xi = x[i]
        if np.isnan(xi):
            have = False
            run = 0
            acc = 0.0
            continue
        if have:
            y = alpha * xi + (1.0 - alpha) * y
            out[i] = y
        else:
            run += 1
            acc += xi
            if run > n:
                acc -= x[i - n]
            if run >= n:
                y = acc / n
                out[i] = y
                have = True
    return out


def ema(x, n):
    n = int(n)
    return _ewm(f64(x), 2.0 / (n + 1), n)


def rma(x, n):
    n = int(n)
    return _ewm(f64(x), 1.0 / n, n)


def tr(h, l, c, handle_na=True):
    """ta.tr(handle_na): на первом баре — high − low (handle_na=True, так считает ta.atr) или na (переменная tr
    в Pine v1–v4 и ta.tr без аргумента)."""
    h, l, c = f64(h), f64(l), f64(c)
    pc = shift(c)
    out = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    out[np.isnan(pc)] = (h - l)[np.isnan(pc)] if handle_na else np.nan
    return out


def atr(h, l, c, n):
    return rma(tr(h, l, c), n)


def rsi(x, n):
    x = f64(x)
    ch = change(x)
    up = rma(np.where(np.isnan(ch), np.nan, np.maximum(ch, 0.0)), n)
    dn = rma(np.where(np.isnan(ch), np.nan, np.maximum(-ch, 0.0)), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = 100.0 - 100.0 / (1.0 + up / dn)
    r = np.where(dn == 0, 100.0, np.where(up == 0, 0.0, r))
    r[np.isnan(up) | np.isnan(dn)] = np.nan
    return r


def stoch(c, h, l, n):
    ll, hh = lowest(l, n), highest(h, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(hh - ll > 0, 100.0 * (f64(c) - ll) / (hh - ll), np.nan)


def cci(x, n):
    x = f64(x)
    with np.errstate(divide="ignore", invalid="ignore"):
        return (x - sma(x, n)) / (0.015 * dev(x, n))


def mfi(src, vol, n):
    """ta.mfi: денежный поток src·volume по знаку изменения src."""
    src, vol = f64(src), f64(vol)
    ch = change(src)
    mf = src * vol
    up = ssum(np.where(ch > 0, mf, 0.0) * np.where(np.isnan(ch), np.nan, 1.0), n)
    dn = ssum(np.where(ch < 0, mf, 0.0) * np.where(np.isnan(ch), np.nan, 1.0), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        return 100.0 - 100.0 / (1.0 + up / dn)


def dmi(h, l, c, di_len, adx_len):
    """ta.dmi: (+DI, −DI, ADX) со сглаживанием rma."""
    h, l = f64(h), f64(l)
    up = change(h)
    dn = -change(l)
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    pdm[np.isnan(up)] = np.nan
    mdm[np.isnan(up)] = np.nan
    trr = rma(tr(h, l, c), di_len)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = 100.0 * rma(pdm, di_len) / trr
        m = 100.0 * rma(mdm, di_len) / trr
        s = p + m
        adx = 100.0 * rma(np.abs(p - m) / np.where(s == 0, 1.0, s), adx_len)
    return p, m, adx


def _pair(a, b):
    return np.broadcast_arrays(f64(a), f64(b))


def crossover(a, b):
    a, b = _pair(a, b)
    with np.errstate(invalid="ignore"):
        return (a > b) & (shift(a) <= shift(b))


def crossunder(a, b):
    a, b = _pair(a, b)
    with np.errstate(invalid="ignore"):
        return (a < b) & (shift(a) >= shift(b))


def cross(a, b):
    return crossover(a, b) | crossunder(a, b)


def pivothigh(x, left, right):
    """ta.pivothigh: на баре i = центр + right — значение центра, если оно строго выше left баров слева
    и не ниже right баров справа; иначе NaN."""
    x = f64(x)
    n = len(x)
    out = np.full(n, np.nan)
    w = left + right + 1
    if n < w:
        return out
    W = _sw(x, w)
    ctr = W[:, left]
    ok = np.ones(len(W), bool)
    if left:
        ok &= ctr > W[:, :left].max(axis=1)
    if right:
        ok &= ctr >= W[:, left + 1:].max(axis=1)
    ok &= ~np.isnan(ctr)
    out[w - 1:][ok] = ctr[ok]
    return out


def pivotlow(x, left, right):
    x = f64(x)
    n = len(x)
    out = np.full(n, np.nan)
    w = left + right + 1
    if n < w:
        return out
    W = _sw(x, w)
    ctr = W[:, left]
    ok = np.ones(len(W), bool)
    if left:
        ok &= ctr < W[:, :left].min(axis=1)
    if right:
        ok &= ctr <= W[:, left + 1:].min(axis=1)
    ok &= ~np.isnan(ctr)
    out[w - 1:][ok] = ctr[ok]
    return out


def fixnan(x):
    """fixnan: NaN заменяется последним известным значением."""
    x = f64(x)
    idx = np.where(~np.isnan(x), np.arange(len(x)), 0)
    np.maximum.accumulate(idx, out=idx)
    out = x[idx]
    first = np.flatnonzero(~np.isnan(x))
    if len(first):
        out[:first[0]] = np.nan
    return out


def valuewhen_last(cond, src):
    """ta.valuewhen(cond, src, 0): src на последнем баре, где cond истинно (включая текущий)."""
    return fixnan(np.where(np.asarray(cond, bool), f64(src), np.nan))


def barssince(cond):
    """ta.barssince: баров с последнего истинного cond (0 — на текущем); до первого — NaN."""
    cond = np.asarray(cond, bool)
    i = np.arange(len(cond))
    last = np.where(cond, i, -1)
    np.maximum.accumulate(last, out=last)
    out = (i - last).astype(np.float64)
    out[last < 0] = np.nan
    return out


def heikin_ashi(o, h, l, c):
    o, h, l, c = f64(o), f64(h), f64(l), f64(c)
    hc = (o + h + l + c) / 4.0
    ho = _ha_open(o, c, hc)
    return ho, np.maximum(h, np.maximum(ho, hc)), np.minimum(l, np.minimum(ho, hc)), hc


@njit(cache=True)
def _ha_open(o, c, hc):
    out = np.empty(o.size)
    for i in range(o.size):
        out[i] = (o[i] + c[i]) / 2.0 if i == 0 else (out[i - 1] + hc[i - 1]) / 2.0
    return out


def flips(state):
    """Смена состояния тренда: (вверх, вниз) — бар, где state стал > 0 / < 0 после противоположного."""
    s = f64(state)
    ps = shift(s)
    return (s > 0) & (ps < 0), (s < 0) & (ps > 0)
