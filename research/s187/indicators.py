"""s187 — повторение популярных скриптов TradingView на Python (свой код, не копия Pine).

Каждая функция получает массивы закрытых свечей o, h, l, c, v (float64, бар i — закрытая свеча i; v — объём в монетах)
и настройки автора по умолчанию; возвращает словарь: buy, sell — булевы массивы сигналов на закрытии бара i
(по данным баров 0…i, без будущих значений) и рабочие ряды для проверки формул.

Реестр REG: имя → функция и паспорт (автор, ссылка, бусты на 19.11.2026, блоки, правило сигнала, таймфрейм автора,
прогрев в барах). Проверка формул, «нет заглядывания вперёд» и частоты — check.py.

Блоки: MA — скользящие средние/тренд, OSC — осцилляторы, VOLA — полосы и волатильность (ATR), VOL — объём и поток,
STRUCT — структура/пивоты/SMC, ML — регрессия ядром и машинное обучение, PAT — свечные фигуры."""
import numpy as np

import pine as P
from pine import njit

REG = {}


def register(name, **meta):
    def deco(fn):
        REG[name] = dict(fn=fn, name=name, **meta)
        return fn
    return deco


def _first(cond):
    """Первый бар серии условия: cond and not cond[1]."""
    cond = np.asarray(cond, bool)
    return cond & ~np.r_[False, cond[:-1]]


def _gt(a, b):
    with np.errstate(invalid="ignore"):
        return np.asarray(a > b, bool)


def _lt(a, b):
    with np.errstate(invalid="ignore"):
        return np.asarray(a < b, bool)


TV = "https://www.tradingview.com/script/"


# ---------------------------------------------------------------------------------------------------------------
# 1. Smart Money Concepts [LuxAlgo] — структура BOS/CHoCH
# ---------------------------------------------------------------------------------------------------------------
@njit(cache=True)
def _smc_core(h, l, c, swing_len, int_len):
    n = c.size
    out = np.zeros((8, n), np.bool_)        # iBOS↑ iCHoCH↑ iBOS↓ iCHoCH↓ sBOS↑ sCHoCH↑ sBOS↓ sCHoCH↓
    lvl = np.full(4, np.nan)                # swingHigh, swingLow, internalHigh, internalLow
    crossed = np.zeros(4, np.bool_)
    prev_lvl = np.full(4, np.nan)
    leg = np.zeros(2, np.int64)             # swing, internal: 0 — медвежья нога, 1 — бычья
    bias = np.zeros(2, np.int64)            # тренд структуры: +1/−1/0
    for i in range(n):
        for k in range(2):                  # 0 — swing (50), 1 — internal (5); порядок как в скрипте
            size = swing_len if k == 0 else int_len
            if i < size:
                continue
            hh = -np.inf
            ll = np.inf
            for j in range(i - size + 1, i + 1):
                if h[j] > hh:
                    hh = h[j]
                if l[j] < ll:
                    ll = l[j]
            old = leg[k]
            if h[i - size] > hh:
                leg[k] = 0
            elif l[i - size] < ll:
                leg[k] = 1
            if leg[k] != old:
                if leg[k] == 1:             # начало бычьей ноги → пивот-минимум low[size]
                    lvl[2 * k + 1] = l[i - size]
                    crossed[2 * k + 1] = False
                else:                       # начало медвежьей ноги → пивот-максимум high[size]
                    lvl[2 * k] = h[i - size]
                    crossed[2 * k] = False
        for k in (1, 0):                    # displayStructure(internal) затем displayStructure(swing)
            hi, lo = 2 * k, 2 * k + 1
            base = 0 if k == 1 else 4
            if i > 0:
                ok_hi = True
                ok_lo = True
                if k == 1:
                    ok_hi = (not np.isnan(lvl[0])) and lvl[2] != lvl[0]
                    ok_lo = (not np.isnan(lvl[1])) and lvl[3] != lvl[1]
                if (not crossed[hi]) and ok_hi and c[i] > lvl[hi] and c[i - 1] <= prev_lvl[hi]:
                    if bias[k] == -1:
                        out[base + 1, i] = True
                    else:
                        out[base + 0, i] = True
                    crossed[hi] = True
                    bias[k] = 1
                if (not crossed[lo]) and ok_lo and c[i] < lvl[lo] and c[i - 1] >= prev_lvl[lo]:
                    if bias[k] == 1:
                        out[base + 3, i] = True
                    else:
                        out[base + 2, i] = True
                    crossed[lo] = True
                    bias[k] = -1
        for m in range(4):
            prev_lvl[m] = lvl[m]
    return out


@register("smc_luxalgo", title="Smart Money Concepts (SMC) [LuxAlgo]", author="LuxAlgo", url=TV + "CnB3fSph/",
          boosts=182657, blocks=["STRUCT"], tf="2h (график публикации), любой", warmup=300,
          signal="внутренняя структура (5): бычий CHoCH — buy, медвежий CHoCH — sell (без BOS)",
          repaint="нет: событие — пересечение close уровня подтверждённого пивота; метка рисуется у пивота в прошлом")
def smc_luxalgo(o, h, l, c, v, swing_len=50, internal_len=5, mode="internal_choch"):
    """Smart Money Concepts [LuxAlgo], https://www.tradingview.com/script/CnB3fSph/.
    Нога: high[size] > highest(size) → медвежья, low[size] < lowest(size) → бычья; смена ноги даёт пивот
    (виден через size баров). BOS/CHoCH — close пересекает последний неотработанный пивот; CHoCH, если прежний
    тренд структуры был противоположным. Внутренняя структура (5) не отмечается, если её уровень совпал со swing (50).
    mode: internal_choch | internal_all | swing_all."""
    S = _smc_core(P.f64(h), P.f64(l), P.f64(c), int(swing_len), int(internal_len))
    res = dict(i_bos_buy=S[0], i_choch_buy=S[1], i_bos_sell=S[2], i_choch_sell=S[3],
               s_bos_buy=S[4], s_choch_buy=S[5], s_bos_sell=S[6], s_choch_sell=S[7])
    if mode == "internal_choch":
        res["buy"], res["sell"] = S[1].copy(), S[3].copy()
    elif mode == "internal_all":
        res["buy"], res["sell"] = S[0] | S[1], S[2] | S[3]
    else:
        res["buy"], res["sell"] = S[4] | S[5], S[6] | S[7]
    return res


# ---------------------------------------------------------------------------------------------------------------
# 2. Squeeze Momentum Indicator [LazyBear]
# ---------------------------------------------------------------------------------------------------------------
@register("squeeze_lb", title="Squeeze Momentum Indicator [LazyBear]", author="LazyBear", url=TV + "nqQ1DT5a/",
          boosts=118375, blocks=["VOLA", "OSC"], tf="6h (график публикации), любой", warmup=60,
          signal="выход из сжатия (первый серый крест после чёрного): val > 0 — buy, val < 0 — sell",
          repaint="нет")
def squeeze_lb(o, h, l, c, v, length=20, mult=2.0, length_kc=20, mult_kc=1.5, use_tr=True, fix_typo=False):
    """Squeeze Momentum [LazyBear], https://www.tradingview.com/script/nqQ1DT5a/ (по мотивам TTM Squeeze, Carter).
    BB: sma(c, 20) ± k·stdev(c, 20); в опубликованном коде k = multKC = 1,5 (опечатка автора, fix_typo=True — 2,0).
    KC: sma(c, 20) ± 1,5·sma(tr, 20). sqzOn — BB внутри KC, sqzOff — BB снаружи.
    val = linreg(c − ((highest(h,20) + lowest(l,20))/2 + sma(c,20))/2, 20, 0).
    Сигнал (правило Картера из описания): первый sqzOff после sqzOn (бары без состояния пропускаются),
    направление — знак val."""
    c = P.f64(c)
    basis = P.sma(c, length)
    dev = (mult if fix_typo else mult_kc) * P.stdev(c, length)
    ma = P.sma(c, length_kc)
    rng = P.tr(h, l, c, handle_na=False) if use_tr else P.f64(h) - P.f64(l)
    rma_ = P.sma(rng, length_kc)
    up_bb, lo_bb = basis + dev, basis - dev
    up_kc, lo_kc = ma + rma_ * mult_kc, ma - rma_ * mult_kc
    on = _gt(lo_bb, lo_kc) & _lt(up_bb, up_kc)
    off = _lt(lo_bb, lo_kc) & _gt(up_bb, up_kc)
    val = P.linreg(c - ((P.highest(h, length_kc) + P.lowest(l, length_kc)) / 2 + P.sma(c, length_kc)) / 2,
                   length_kc, 0)
    st = np.where(on, 1, np.where(off, -1, 0))
    last = np.zeros_like(st)
    cur = 0
    for i in range(len(st)):               # последнее ненулевое состояние до бара i (не включая)
        last[i] = cur
        if st[i] != 0:
            cur = st[i]
    release = off & (last == 1)
    return dict(buy=release & _gt(val, 0), sell=release & _lt(val, 0), val=val, sqz_on=on, sqz_off=off)


# ---------------------------------------------------------------------------------------------------------------
# 3. SuperTrend [KivancOzbilgic]
# ---------------------------------------------------------------------------------------------------------------
@njit(cache=True)
def _st_kivanc(src, c, atr, mult):
    n = c.size
    up = np.full(n, np.nan)
    dn = np.full(n, np.nan)
    trend = np.ones(n)
    t = 1.0
    for i in range(n):
        u = src[i] - mult * atr[i]
        d = src[i] + mult * atr[i]
        u1 = up[i - 1] if (i > 0 and not np.isnan(up[i - 1])) else u
        d1 = dn[i - 1] if (i > 0 and not np.isnan(dn[i - 1])) else d
        if i > 0 and c[i - 1] > u1:
            u = u if u > u1 else u1
        if i > 0 and c[i - 1] < d1:
            d = d if d < d1 else d1
        if t == -1.0 and c[i] > d1:
            t = 1.0
        elif t == 1.0 and c[i] < u1:
            t = -1.0
        up[i] = u
        dn[i] = d
        trend[i] = t
    return up, dn, trend


@register("supertrend_kivanc", title="SuperTrend", author="KivancOzbilgic", url=TV + "r6dAP7yi/", boosts=85966,
          blocks=["VOLA", "MA"], tf="1D (график публикации), любой", warmup=50,
          signal="смена тренда: −1→1 buy, 1→−1 sell (метки Buy/Sell, alertcondition)", repaint="нет")
def supertrend_kivanc(o, h, l, c, v, periods=10, mult=3.0, change_atr=True):
    """SuperTrend [KivancOzbilgic], https://www.tradingview.com/script/r6dAP7yi/.
    up = hl2 − m·ATR, dn = hl2 + m·ATR (ATR = rma(tr,10); при changeATR=false — sma(tr,10)); полосы подтягиваются
    за ценой; тренд −1 → 1 при close > dn[1], 1 → −1 при close < up[1]."""
    h, l, c = P.f64(h), P.f64(l), P.f64(c)
    atr = P.atr(h, l, c, periods) if change_atr else P.sma(P.tr(h, l, c, False), periods)
    up, dn, trend = _st_kivanc((h + l) / 2, c, atr, float(mult))
    ps = P.shift(trend)
    return dict(buy=(trend == 1) & (ps == -1), sell=(trend == -1) & (ps == 1), up=up, dn=dn, trend=trend)


# ---------------------------------------------------------------------------------------------------------------
# 4. MacD Custom Indicator-Multiple Time Frame [ChrisMoody]
# ---------------------------------------------------------------------------------------------------------------
@register("macd_cm", title="MacD Custom Indicator-Multiple Time Frame+All Available Options!", author="ChrisMoody",
          url=TV + "OQx7vju0/", boosts=82984, blocks=["MA", "OSC"], tf="1D (график публикации), любой", warmup=120,
          signal="точка на пересечении MACD и сигнальной: вверх — buy, вниз — sell (сигнальная — SMA 9)",
          repaint="нет на своём таймфрейме; на старшем — security() Pine v1 с заглядыванием (lookahead по умолчанию)")
def macd_cm(o, h, l, c, v, fast=12, slow=26, signal=9):
    """CM_MacD_Ult_MTF [ChrisMoody], https://www.tradingview.com/script/OQx7vju0/.
    macd = ema(c,12) − ema(c,26); signal = sma(macd, 9) (не EMA, как у встроенного); точки — cross(macd, signal)."""
    c = P.f64(c)
    m = P.ema(c, fast) - P.ema(c, slow)
    s = P.sma(m, signal)
    return dict(buy=P.crossover(m, s), sell=P.crossunder(m, s), macd=m, signal=s)


# ---------------------------------------------------------------------------------------------------------------
# 5. Support and Resistance Levels with Breaks [LuxAlgo]
# ---------------------------------------------------------------------------------------------------------------
@register("sr_breaks_luxalgo", title="Support and Resistance Levels with Breaks [LuxAlgo]", author="LuxAlgo",
          url=TV + "JDFoWQbL/", boosts=68285, blocks=["STRUCT", "VOL"], tf="4h (график публикации)", warmup=60,
          signal="alertcondition: close пересёк вверх последний пивот-максимум (15/15) при осцилляторе объёма > 20% — buy;"
                 " вниз последний пивот-минимум — sell",
          repaint="нет: уровни — пивоты, подтверждённые через 15 баров (линии рисуются со сдвигом −16 баров)")
def sr_breaks_luxalgo(o, h, l, c, v, left=15, right=15, vol_thresh=20.0, use_wick_filter=False):
    """Support and Resistance Levels with Breaks [LuxAlgo], https://www.tradingview.com/script/JDFoWQbL/.
    R = fixnan(pivothigh(15,15)[1]), S = fixnan(pivotlow(15,15)[1]); osc = 100·(ema(v,5) − ema(v,10))/ema(v,10).
    buy: crossover(c, R) и osc > 20; sell: crossunder(c, S) и osc > 20 (как в alertcondition; метки «B» на графике
    дополнительно отсекают пробои с длинной тенью — use_wick_filter=True)."""
    o, h, l, c, v = (P.f64(x) for x in (o, h, l, c, v))
    R = P.fixnan(P.shift(P.pivothigh(h, left, right), 1))
    S = P.fixnan(P.shift(P.pivotlow(l, left, right), 1))
    s5, s10 = P.ema(v, 5), P.ema(v, 10)
    with np.errstate(divide="ignore", invalid="ignore"):
        osc = 100 * (s5 - s10) / s10
    buy = P.crossover(c, R) & _gt(osc, vol_thresh)
    sell = P.crossunder(c, S) & _gt(osc, vol_thresh)
    if use_wick_filter:
        buy &= ~_gt(o - l, c - o)
        sell &= ~_lt(o - c, h - o)
    return dict(buy=buy, sell=sell, R=R, S=S, osc=osc)


# ---------------------------------------------------------------------------------------------------------------
# 6. CM_Williams_Vix_Fix [ChrisMoody]
# ---------------------------------------------------------------------------------------------------------------
@register("vixfix_cm", title="CM_Williams_Vix_Fix Finds Market Bottoms", author="ChrisMoody", url=TV + "og7JPrRA/",
          boosts=66308, blocks=["VOLA"], tf="1D (по описанию), «работает и внутри дня»", warmup=80,
          signal="первая зелёная (lime) свеча гистограммы: wvf ≥ BB-верх или ≥ 0,85·max(wvf,50) — buy; продаж нет",
          repaint="нет")
def vixfix_cm(o, h, l, c, v, pd=22, bbl=20, mult=2.0, lb=50, ph=0.85):
    """CM_Williams_Vix_Fix [ChrisMoody], https://www.tradingview.com/script/og7JPrRA/ (Larry Williams VIX Fix).
    wvf = (highest(c,22) − l)/highest(c,22)·100; верх = sma(wvf,20) + 2·stdev(wvf,20); rangeHigh = 0,85·highest(wvf,50).
    Подсветка дна — wvf ≥ верх или wvf ≥ rangeHigh; сигнал — первый такой бар подряд."""
    c, l = P.f64(c), P.f64(l)
    hc = P.highest(c, pd)
    wvf = (hc - l) / hc * 100
    upper = P.sma(wvf, bbl) + mult * P.stdev(wvf, bbl)
    rh = P.highest(wvf, lb) * ph
    green = (wvf >= upper) | (wvf >= rh)
    green &= ~np.isnan(upper) & ~np.isnan(rh)
    return dict(buy=_first(green), sell=np.zeros(len(c), bool), wvf=wvf, upper=upper)


# ---------------------------------------------------------------------------------------------------------------
# 7. Market Structure Break & Order Block [EmreKb]
# ---------------------------------------------------------------------------------------------------------------
@njit(cache=True)
def _msb_core(h, l, zz, fib):
    n = h.size
    market_out = np.ones(n)
    hv = np.full(5, np.nan)                 # массивы Pine создаются с 5 na: последние значения справа
    lv = np.full(5, np.nan)
    hv_n = 5
    lv_n = 5
    hbuf = np.full(n + 5, np.nan)
    lbuf = np.full(n + 5, np.nan)
    hbuf[:5] = hv
    lbuf[:5] = lv
    trend = 1
    market = 1
    mid_prev = np.nan                       # значение market, переданное в ta.change(market) на прошлом баре
    last_l0 = np.nan                        # ta.valuewhen(ta.change(market) != 0, l0, 0)
    last_h0 = np.nan
    last_up = -1                            # последний бар с to_up
    last_dn = -1
    for i in range(n):
        lo = max(0, i - zz + 1)
        hh = -np.inf
        ll = np.inf
        for j in range(lo, i + 1):
            if h[j] > hh:
                hh = h[j]
            if l[j] < ll:
                ll = l[j]
        to_up = h[i] >= hh and i >= zz - 1           # ta.highest(9) — na на первых 8 барах
        to_dn = l[i] <= ll and i >= zz - 1
        old = trend
        if trend == 1 and to_dn:
            trend = -1
        elif trend == -1 and to_up:
            trend = 1
        # barssince(to_up[1]): баров с последнего бара k, где to_up[k−1]
        if trend != old:
            if trend == 1:
                L = (i - (last_up + 1)) if last_up >= 0 else -1
                L = L if L > 0 else 1
                v = np.inf
                for j in range(max(0, i - L + 1), i + 1):
                    if l[j] < v:
                        v = l[j]
                lbuf[lv_n] = v
                lv_n += 1
            else:
                L = (i - (last_dn + 1)) if last_dn >= 0 else -1
                L = L if L > 0 else 1
                v = -np.inf
                for j in range(max(0, i - L + 1), i + 1):
                    if h[j] > v:
                        v = h[j]
                hbuf[hv_n] = v
                hv_n += 1
        if to_up:
            last_up = i
        if to_dn:
            last_dn = i
        h0 = hbuf[hv_n - 1]
        h1 = hbuf[hv_n - 2]
        l0 = lbuf[lv_n - 1]
        l1 = lbuf[lv_n - 2]
        # market := nz(market[1], 1); ta.change(market) видит значения, переданные на этом и прошлом вызове
        # (история аргумента функции) — ненулевое изменение на баре ПОСЛЕ смены market
        mid = market
        if (not np.isnan(mid_prev)) and mid - mid_prev != 0:
            last_l0 = l0
            last_h0 = h0
        mid_prev = mid
        if last_l0 == l0 or last_h0 == h0:
            pass
        elif market == 1 and l0 < l1 and l0 < l1 - abs(h0 - l1) * fib:
            market = -1
        elif market == -1 and h0 > h1 and h0 > h1 + abs(h1 - l0) * fib:
            market = 1
        market_out[i] = market
    return market_out


@register("msb_emrekb", title="Market Structure Break & Order Block by EmreKb", author="EmreKb", url=TV + "DkE7UniD/",
          boosts=65491, blocks=["STRUCT"], tf="5m (график публикации), любой", warmup=50,
          signal="смена market (метка MSB): −1→1 buy, 1→−1 sell", repaint="нет: зигзаг подтверждается текущим баром")
def msb_emrekb(o, h, l, c, v, zigzag_len=9, fib_factor=0.33):
    """Market Structure Break & Order Block [EmreKb], https://www.tradingview.com/script/DkE7UniD/.
    Зигзаг: to_up = high ≥ highest(9), to_down = low ≤ lowest(9); при смене тренда в массивы пишется минимум/максимум
    участка. MSB вверх: market = −1 и h0 > h1 + |h1 − l0|·0,33; вниз: market = 1 и l0 < l1 − |h0 − l1|·0,33.
    После смены market состояние заморожено, пока не обновятся и последний максимум h0, и последний минимум l0
    (ta.valuewhen(ta.change(market) != 0, …) срабатывает на баре после смены — история аргумента функции Pine)."""
    m = _msb_core(P.f64(h), P.f64(l), int(zigzag_len), float(fib_factor))
    pm = P.shift(m)
    return dict(buy=(m == 1) & (pm == -1), sell=(m == -1) & (pm == 1), market=m)


# ---------------------------------------------------------------------------------------------------------------
# 8. UT Bot Alerts [QuantNomad]
# ---------------------------------------------------------------------------------------------------------------
@njit(cache=True)
def _ut_core(src, nloss):
    n = src.size
    ts = np.full(n, np.nan)
    for i in range(n):
        p = ts[i - 1] if (i > 0 and not np.isnan(ts[i - 1])) else 0.0
        s1 = src[i - 1] if i > 0 else np.nan
        if src[i] > p and s1 > p:
            x = src[i] - nloss[i]
            ts[i] = p if p > x else x
            if np.isnan(x):
                ts[i] = np.nan
        elif src[i] < p and s1 < p:
            x = src[i] + nloss[i]
            ts[i] = p if p < x else x
            if np.isnan(x):
                ts[i] = np.nan
        elif src[i] > p:
            ts[i] = src[i] - nloss[i]
        else:
            ts[i] = src[i] + nloss[i]
    return ts


@register("ut_bot", title="UT Bot Alerts", author="QuantNomad", url=TV + "n8ss8BID/", boosts=62609,
          blocks=["VOLA"], tf="1h (график публикации), любой", warmup=50,
          signal="close пересёк ATR-стоп (a=1, ATR 10): вверх — buy, вниз — sell", repaint="нет (без Heikin Ashi)")
def ut_bot(o, h, l, c, v, key=1.0, atr_period=10):
    """UT Bot Alerts [QuantNomad], https://www.tradingview.com/script/n8ss8BID/.
    nLoss = a·atr(10); стоп тянется за close (max/min с прошлым стопом, пока цена по одну сторону), иначе
    переворачивается на close ∓ nLoss. buy: close > стоп и crossover(close, стоп); sell — наоборот."""
    h, l, c = P.f64(h), P.f64(l), P.f64(c)
    ts = _ut_core(c, key * P.atr(h, l, c, atr_period))
    return dict(buy=_gt(c, ts) & P.crossover(c, ts), sell=_lt(c, ts) & P.crossover(ts, c), stop=ts)


# ---------------------------------------------------------------------------------------------------------------
# 9. WaveTrend Oscillator [LazyBear] и VuManChu Cipher B
# ---------------------------------------------------------------------------------------------------------------
def _wavetrend(h, l, c, n1, n2, ma_len):
    ap = (P.f64(h) + P.f64(l) + P.f64(c)) / 3
    esa = P.ema(ap, n1)
    d = P.ema(np.abs(ap - esa), n1)
    with np.errstate(divide="ignore", invalid="ignore"):
        ci = (ap - esa) / (0.015 * d)
    wt1 = P.ema(ci, n2)
    return wt1, P.sma(wt1, ma_len)


@register("wavetrend_lb", title="Indicator: WaveTrend Oscillator [WT]", author="LazyBear", url=TV + "2KE8wTuF/",
          boosts=61666, blocks=["OSC"], tf="4h (график публикации), любой", warmup=120,
          signal="wt1 пересекает wt2 вверх при wt2 ≤ −53 — buy, вниз при wt2 ≥ 53 — sell (правило из описания)",
          repaint="нет")
def wavetrend_lb(o, h, l, c, v, n1=10, n2=21, ob=53.0, os_=-53.0):
    """WaveTrend [LazyBear], https://www.tradingview.com/script/2KE8wTuF/.
    ap = hlc3; esa = ema(ap,10); d = ema(|ap − esa|,10); ci = (ap − esa)/(0,015·d); wt1 = ema(ci,21); wt2 = sma(wt1,4).
    Сигнал по описанию автора: пересечение wt1/wt2 вверх ниже зоны перепроданности (−53, вторая линия),
    вниз — выше перекупленности (53). Скрипт сам меток не ставит."""
    wt1, wt2 = _wavetrend(h, l, c, n1, n2, 4)
    return dict(buy=P.crossover(wt1, wt2) & (wt2 <= os_), sell=P.crossunder(wt1, wt2) & (wt2 >= ob), wt1=wt1, wt2=wt2)


@register("cipher_b", title="VuManChu Cipher B + Divergences", author="vumanchu", url=TV + "Msm4SjwI/", boosts=25015,
          blocks=["OSC"], tf="1h (график публикации), любой", warmup=120,
          signal="зелёный/красный кружок: cross(wt1, wt2) вверх при wt2 ≤ −53 — buy, вниз при wt2 ≥ 53 — sell",
          repaint="кружки — нет; точки дивергенций и «золотые» рисуются со сдвигом −2 бара (видны через 2 бара)")
def cipher_b(o, h, l, c, v, chlen=9, avg=12, malen=3, ob=53.0, os_=-53.0):
    """VuManChu Cipher B (открытая копия Market Cipher B), https://www.tradingview.com/script/Msm4SjwI/.
    WaveTrend 9/12/3 по hlc3: buy = cross(wt1,wt2) и wt2 − wt1 ≤ 0 и wt2 ≤ −53; sell = cross и wt2 − wt1 ≥ 0 и wt2 ≥ 53."""
    wt1, wt2 = _wavetrend(h, l, c, chlen, avg, malen)
    x = P.cross(wt1, wt2)
    return dict(buy=x & ((wt2 - wt1) <= 0) & (wt2 <= os_), sell=x & ((wt2 - wt1) >= 0) & (wt2 >= ob), wt1=wt1, wt2=wt2)


# ---------------------------------------------------------------------------------------------------------------
# 10. Trendlines with Breaks [LuxAlgo]
# ---------------------------------------------------------------------------------------------------------------
@njit(cache=True)
def _tl_core(c, ph, pl, slope, length):
    n = c.size
    upos = np.zeros(n)
    dnos = np.zeros(n)
    sp = 0.0
    sl = 0.0
    upper = 0.0
    lower = 0.0
    u = 0.0
    d = 0.0
    for i in range(n):
        hasph = (not np.isnan(ph[i])) and ph[i] != 0
        haspl = (not np.isnan(pl[i])) and pl[i] != 0
        if hasph:
            sp = slope[i]
        if haspl:
            sl = slope[i]
        upper = ph[i] if hasph else upper - sp
        lower = pl[i] if haspl else lower + sl
        if hasph:
            u = 0.0
        elif c[i] > upper - sp * length:
            u = 1.0
        if haspl:
            d = 0.0
        elif c[i] < lower + sl * length:
            d = 1.0
        upos[i] = u
        dnos[i] = d
    return upos, dnos


@register("trendlines_luxalgo", title="Trendlines with Breaks [LuxAlgo]", author="LuxAlgo", url=TV + "IYL88A1N/",
          boosts=54455, blocks=["STRUCT", "VOLA"], tf="1D (график публикации), любой", warmup=60,
          signal="пробой нисходящей линии от пивот-максимума (14/14, наклон ATR/14) — buy (upos > upos[1]);"
                 " восходящей от пивот-минимума — sell",
          repaint="метки — нет; линии по умолчанию «backpainting» сдвинуты на 14 баров назад (видны позже)")
def trendlines_luxalgo(o, h, l, c, v, length=14, mult=1.0):
    """Trendlines with Breaks [LuxAlgo], https://www.tradingview.com/script/IYL88A1N/.
    От пивота (подтверждён через 14 баров) линия идёт с наклоном atr(14)/14·mult; текущий уровень линии —
    upper − slope·14. Пробой: close выше уровня (upos 0→1) / ниже (dnos 0→1)."""
    h, l, c = P.f64(h), P.f64(l), P.f64(c)
    slope = P.atr(h, l, c, length) / length * mult
    upos, dnos = _tl_core(c, P.pivothigh(h, length, length), P.pivotlow(l, length, length), slope, float(length))
    return dict(buy=upos > P.nz(P.shift(upos)), sell=dnos > P.nz(P.shift(dnos)), upos=upos, dnos=dnos)


# ---------------------------------------------------------------------------------------------------------------
# 11. ADX and DI [BeikabuOyaji]
# ---------------------------------------------------------------------------------------------------------------
@njit(cache=True)
def _wilder_sum(x, n):
    out = np.empty(x.size)
    s = 0.0
    for i in range(x.size):
        s = s - s / n + x[i]
        out[i] = s
    return out


@register("adx_di", title="ADX and DI", author="BeikabuOyaji", url=TV + "VTPMMOrx/", boosts=45610,
          blocks=["OSC"], tf="5m (график публикации), любой", warmup=100,
          signal="(скрипт без меток; общепринятое правило) DI+ пересекает DI− вверх при ADX > 20 — buy, вниз — sell",
          repaint="нет")
def adx_di(o, h, l, c, v, length=14, th=20.0):
    """ADX and DI [BeikabuOyaji], https://www.tradingview.com/script/VTPMMOrx/.
    TR и DM с nz() на первом баре; сглаживание Уайлдера суммой s = s − s/14 + x; DI± = 100·DM±/TR;
    DX = |DI+ − DI−|/(DI+ + DI−)·100; ADX = sma(DX, 14) (не rma)."""
    h, l, c = P.f64(h), P.f64(l), P.f64(c)
    pc, ph_, pl_ = P.nz(P.shift(c)), P.nz(P.shift(h)), P.nz(P.shift(l))
    trr = np.maximum(np.maximum(h - l, np.abs(h - pc)), np.abs(l - pc))
    up, dn = h - ph_, pl_ - l
    dmp = np.where(up > dn, np.maximum(up, 0), 0.0)
    dmm = np.where(dn > up, np.maximum(dn, 0), 0.0)
    st, sp, sm = (_wilder_sum(x, float(length)) for x in (trr, dmp, dmm))
    with np.errstate(divide="ignore", invalid="ignore"):
        dip, dim = sp / st * 100, sm / st * 100
        dx = np.abs(dip - dim) / (dip + dim) * 100
    adx = P.sma(dx, length)
    return dict(buy=P.crossover(dip, dim) & _gt(adx, th), sell=P.crossunder(dip, dim) & _gt(adx, th),
                dip=dip, dim=dim, adx=adx)


# ---------------------------------------------------------------------------------------------------------------
# 12. Machine Learning: Lorentzian Classification [jdehorty]
# ---------------------------------------------------------------------------------------------------------------
@njit(cache=True)
def _normalize_expanding(x):
    out = np.full(x.size, np.nan)
    mn = 10e10
    mx = -10e10
    for i in range(x.size):
        if not np.isnan(x[i]):
            if x[i] < mn:
                mn = x[i]
            if x[i] > mx:
                mx = x[i]
            r = mx - mn
            out[i] = (x[i] - mn) / (r if r > 10e-10 else 10e-10)
    return out


@njit(cache=True)
def _regime_klmf(src, h, l):
    """KLMF из MLExtensions.regime_filter: value1, value2, klmf с nz() прошлых значений (старт от нуля)."""
    n = src.size
    v1p = 0.0
    v2p = 0.0
    kp = 0.0
    klmf = np.full(n, np.nan)
    for i in range(n):
        d = src[i] - src[i - 1] if i > 0 else np.nan
        v1 = 0.2 * d + 0.8 * v1p
        v2 = 0.1 * (h[i] - l[i]) + 0.8 * v2p
        om = abs(v1 / v2) if v2 != 0 else np.nan
        al = (-om ** 2 + np.sqrt(om ** 4 + 16 * om ** 2)) / 8
        k = al * src[i] + (1 - al) * kp
        klmf[i] = k
        v1p = v1 if not np.isnan(v1) else 0.0
        v2p = v2 if not np.isnan(v2) else 0.0
        kp = k if not np.isnan(k) else 0.0
    return klmf


@njit(cache=True)
def _lorentzian_core(F, y, ok_from, max_back, k_nb):
    """Приближённые соседи как в скрипте: окно — max_back прошлых баров по порядку времени, индексы i % 4 == 0
    пропускаются, кандидат берётся при d ≥ lastDistance; массивы соседей переходят с бара на бар (var)."""
    n = F.shape[0]
    nf = F.shape[1]
    pred = np.zeros(n)
    dists = np.zeros(k_nb + 1)
    preds = np.zeros(k_nb + 1)
    cnt = 0
    for b in range(n):
        if b < ok_from:
            continue
        last = -1.0
        start = b - max_back if b - max_back > 0 else 0
        for i in range(start, b):
            if i % 4 == 0:
                continue
            d = 0.0
            bad = False
            for f in range(nf):
                a = F[b, f]
                q = F[i, f]
                if np.isnan(a) or np.isnan(q):
                    bad = True
                    break
                d += np.log(1.0 + abs(a - q))
            if bad or np.isnan(y[i]):
                continue
            if d >= last:
                last = d
                dists[cnt] = d
                preds[cnt] = y[i]
                cnt += 1
                if cnt > k_nb:
                    last = dists[int(round(k_nb * 3 / 4))]
                    for j in range(k_nb):
                        dists[j] = dists[j + 1]
                        preds[j] = preds[j + 1]
                    cnt = k_nb
        s = 0.0
        for j in range(cnt):
            s += preds[j]
        pred[b] = s
    return pred


def _rq_kernel(x, h=8, r=8.0, start=25):
    w = (1 + (np.arange(start + 2) ** 2) / (h * h * 2 * r)) ** (-r)
    return _causal_kernel(x, w)


def _gauss_kernel(x, h=6, start=25):
    w = np.exp(-(np.arange(start + 2) ** 2) / (2 * h * h))
    return _causal_kernel(x, w)


def _causal_kernel(x, w):
    """Σ x[i−j]·w[j] / Σ w[j], j = 0…len(w)−1 (i — текущий бар); до набора истории — NaN."""
    x = P.f64(x)
    m = len(w)
    out = np.full(len(x), np.nan)
    if len(x) >= m:
        out[m - 1:] = P._sw(x, m) @ w[::-1] / w.sum()
    return out


@register("lorentzian_jdehorty", title="Machine Learning: Lorentzian Classification", author="jdehorty",
          url=TV + "WhBzgfDu/", boosts=37719, blocks=["ML", "OSC"], tf="12h (график публикации), автор — 4h–12h",
          warmup=600,
          signal="startLongTrade: прогноз kNN сменился на long, фильтры волатильности и режима пройдены, ядро RQ растёт"
                 " — buy; зеркально sell",
          repaint="да в исходнике: окно обучения и начало прогнозов от last_bar_index (зависят от длины истории);"
                  " исправлено — скользящее окно 2000 прошлых баров")
def lorentzian_jdehorty(o, h, l, c, v, neighbors=8, max_back=2000, use_vol_filter=True, use_regime=True,
                        regime_th=-0.1, use_kernel=True):
    """Machine Learning: Lorentzian Classification [jdehorty] v2.0, https://www.tradingview.com/script/WhBzgfDu/.
    Признаки (по умолчанию): RSI 14, WT 10/11, CCI 20, ADX 20, RSI 9 — нормированы (RSI/100, WT и CCI — растянутым
    с начала истории min/max, ADX/100). Метка бара i: −1, если close[i−4] < close[i], +1, если больше (так в коде).
    Расстояние — Σ log(1 + |Δ|). Прогноз — сумма меток 8 «соседей» (алгоритм автора, см. _lorentzian_core).
    Сигнал: signal = long при прогнозе > 0 и фильтрах (ATR(1) > ATR(10); KLMF-наклон ≥ −0,1), short при < 0;
    buy — смена signal на long на баре, где ядро rationalQuadratic(8, 8, 25) растёт (yhat1 > yhat1[1]).
    Отличие от TradingView: в скрипте обучение берёт бары [1999, last_bar_index − 2000] (или первые 2000 в v1),
    прогнозы — только на последних 2000 барах графика; здесь — скользящее окно 2000 прошлых баров."""
    o, h, l, c = (P.f64(x) for x in (o, h, l, c))
    hlc3 = (h + l + c) / 3
    f1 = P.ema(P.rsi(c, 14), 1) / 100
    wt1, wt2 = _wavetrend(h, l, c, 10, 11, 4)
    f2 = _normalize_expanding(wt1 - wt2)
    f3 = _normalize_expanding(P.ema(P.cci(c, 20), 1))
    # ADX как в MLExtensions.n_adx: суммы Уайлдера с nz, затем rma(dx, 20)
    pc, ph_, pl_ = P.nz(P.shift(c)), P.nz(P.shift(h)), P.nz(P.shift(l))
    trr = np.maximum(np.maximum(h - l, np.abs(h - pc)), np.abs(l - pc))
    dmp = np.where(h - ph_ > pl_ - l, np.maximum(h - ph_, 0), 0.0)
    dmm = np.where(pl_ - l > h - ph_, np.maximum(pl_ - l, 0), 0.0)
    st, sp, sm = (_wilder_sum(x, 20.0) for x in (trr, dmp, dmm))
    with np.errstate(divide="ignore", invalid="ignore"):
        dip, dim = sp / st * 100, sm / st * 100
        dx = np.abs(dip - dim) / (dip + dim) * 100
    f4 = P.rma(dx, 20) / 100
    f5 = P.ema(P.rsi(c, 9), 1) / 100
    F = np.column_stack([f1, f2, f3, f4, f5])
    ch = c - P.shift(c, 4)
    y = np.where(ch > 0, -1.0, np.where(ch < 0, 1.0, 0.0))     # na-сравнения в Pine ложны → первые 4 бара: 0
    pred = _lorentzian_core(F, y, 0, int(max_back), int(neighbors))
    vol_ok = _gt(P.atr(h, l, c, 1), P.atr(h, l, c, 10)) if use_vol_filter else np.ones(len(c), bool)
    if use_regime:
        ohlc4 = (o + h + l + c) / 4
        klmf = _regime_klmf(ohlc4, h, l)
        sl_ = np.abs(klmf - P.shift(klmf))
        ea = P.ema(sl_, 200)
        with np.errstate(divide="ignore", invalid="ignore"):
            reg_ok = np.asarray((sl_ - ea) / ea >= regime_th, bool)
    else:
        reg_ok = np.ones(len(c), bool)
    fil = vol_ok & reg_ok
    sig = np.zeros(len(c))
    cur = 0.0
    for i in range(len(c)):
        if pred[i] > 0 and fil[i]:
            cur = 1.0
        elif pred[i] < 0 and fil[i]:
            cur = -1.0
        sig[i] = cur
    changed = sig != P.nz(P.shift(sig))
    yhat1 = _rq_kernel(c)
    bull = _gt(yhat1, P.shift(yhat1)) if use_kernel else np.ones(len(c), bool)
    bear = _lt(yhat1, P.shift(yhat1)) if use_kernel else np.ones(len(c), bool)
    return dict(buy=(sig == 1) & changed & bull, sell=(sig == -1) & changed & bear, pred=pred, signal=sig,
                yhat1=yhat1, f1=f1, f2=f2, f3=f3, f4=f4, f5=f5)


# ---------------------------------------------------------------------------------------------------------------
# 13. Nadaraya-Watson Envelope [LuxAlgo] — неперерисовывающий режим
# ---------------------------------------------------------------------------------------------------------------
@register("nw_envelope_luxalgo", title="Nadaraya-Watson Envelope [LuxAlgo]", author="LuxAlgo", url=TV + "Iko0E2kL/",
          boosts=35708, blocks=["ML", "VOLA"], tf="1h (график публикации), любой", warmup=1000,
          signal="режим без перерисовки: close пересекает нижнюю огибающую вниз — buy (▲), верхнюю вверх — sell (▼)",
          repaint="да по умолчанию (repaint=true: двусторонняя гауссова регрессия по 500 барам на последнем баре, "
                  "метки задним числом); исправимо — режим repaint=false (односторонний вес)")
def nw_envelope_luxalgo(o, h, l, c, v, bw=8.0, mult=3.0, n_back=500):
    """Nadaraya-Watson Envelope [LuxAlgo], https://www.tradingview.com/script/Iko0E2kL/, режим repaint=false.
    out = Σ_{i<500} c[i]·exp(−i²/(2·8²)) / Σ exp(…); mae = 3·sma(|c − out|, 499); полосы out ± mae.
    Сигналы скрипта (контртренд): ▲ — crossunder(c, out − mae) → buy; ▼ — crossover(c, out + mae) → sell."""
    c = P.f64(c)
    w = np.exp(-(np.arange(n_back) ** 2) / (bw * bw * 2))
    out = _causal_kernel(c, w)
    mae = P.sma(np.abs(c - out), n_back - 1) * mult
    return dict(buy=P.crossunder(c, out - mae), sell=P.crossover(c, out + mae), out=out, mae=mae)


# ---------------------------------------------------------------------------------------------------------------
# 14. Machine Learning Adaptive SuperTrend [AlgoAlpha]
# ---------------------------------------------------------------------------------------------------------------
@njit(cache=True)
def _kmeans_vol(vol, period, qh, qm, ql):
    n = vol.size
    cen = np.full(n, np.nan)
    for b in range(n):
        if b < period - 1 or np.isnan(vol[b]) or vol[b] <= 0:
            continue
        w = vol[b - period + 1:b + 1]
        if np.isnan(w).any():
            continue
        lo = w.min()
        hi = w.max()
        a = lo + (hi - lo) * qh
        m = lo + (hi - lo) * qm
        z = lo + (hi - lo) * ql
        for it in range(1000):
            sa = 0.0
            na = 0
            sm = 0.0
            nm = 0
            sz = 0.0
            nz_ = 0
            for x in w:
                d1 = abs(x - a)
                d2 = abs(x - m)
                d3 = abs(x - z)
                if d1 < d2 and d1 < d3:
                    sa += x
                    na += 1
                if d2 < d1 and d2 < d3:
                    sm += x
                    nm += 1
                if d3 < d1 and d3 < d2:
                    sz += x
                    nz_ += 1
            a2 = sa / na if na else np.nan
            m2 = sm / nm if nm else np.nan
            z2 = sz / nz_ if nz_ else np.nan
            same = ((a2 == a) or (np.isnan(a2) and np.isnan(a))) and ((m2 == m) or (np.isnan(m2) and np.isnan(m))) \
                and ((z2 == z) or (np.isnan(z2) and np.isnan(z)))
            a, m, z = a2, m2, z2
            if same:
                break
        da = abs(vol[b] - a)
        dm = abs(vol[b] - m)
        dz = abs(vol[b] - z)
        best = np.nan
        bd = np.inf
        for cc, dd in ((a, da), (m, dm), (z, dz)):     # indexof(min): первый минимальный (NaN пропускаем)
            if not np.isnan(dd) and dd < bd:
                bd = dd
                best = cc
        cen[b] = best
    return cen


@njit(cache=True)
def _pine_supertrend(hl2, c, factor, atr):
    """ta.supertrend: направление −1 — рост, 1 — падение."""
    n = c.size
    st = np.full(n, np.nan)
    dr = np.full(n, np.nan)
    lb_prev = np.nan
    ub_prev = np.nan
    for i in range(n):
        ub = hl2[i] + factor * atr[i]
        lb = hl2[i] - factor * atr[i]
        plb = lb_prev if not np.isnan(lb_prev) else 0.0
        pub = ub_prev if not np.isnan(ub_prev) else 0.0
        cp = c[i - 1] if i > 0 else np.nan
        if not (lb > plb or cp < plb):
            lb = plb
        if not (ub < pub or cp > pub):
            ub = pub
        if i == 0 or np.isnan(atr[i - 1]):
            d = 1.0
        elif st[i - 1] == pub:
            d = -1.0 if c[i] > ub else 1.0
        else:
            d = 1.0 if c[i] < lb else -1.0
        st[i] = lb if d == -1.0 else ub
        dr[i] = d
        lb_prev = lb
        ub_prev = ub
    return st, dr


@register("ml_adaptive_st_algoalpha", title="Machine Learning Adaptive SuperTrend [AlgoAlpha]", author="AlgoAlpha",
          url=TV + "CLk71Qgy/", boosts=31482, blocks=["ML", "VOLA"], tf="3h (график публикации), любой", warmup=150,
          signal="SuperTrend с ATR, равным центру ближайшего из 3 кластеров k-средних ATR за 100 баров:"
                 " dir 1→−1 — buy (▲), −1→1 — sell (▼)", repaint="нет")
def ml_adaptive_st_algoalpha(o, h, l, c, v, atr_len=10, fact=3.0, period=100, qh=0.75, qm=0.5, ql=0.25):
    """Machine Learning Adaptive SuperTrend [AlgoAlpha], https://www.tradingview.com/script/CLk71Qgy/.
    ATR(10); k-средние (3 кластера, старт — 25/50/75% размаха ATR за 100 баров) на каждом баре; ATR SuperTrend
    заменяется центром кластера, ближайшего к текущему ATR; сигнал — crossunder(dir, 0) / crossover(dir, 0)."""
    h, l, c = P.f64(h), P.f64(l), P.f64(c)
    vol = P.atr(h, l, c, atr_len)
    cen = _kmeans_vol(vol, int(period), qh, qm, ql)
    st, dr = _pine_supertrend((h + l) / 2, c, float(fact), cen)
    return dict(buy=P.crossunder(dr, 0), sell=P.crossover(dr, 0), st=st, dir=dr, centroid=cen)


# ---------------------------------------------------------------------------------------------------------------
# 15. SuperTrend AI (Clustering) [LuxAlgo]
# ---------------------------------------------------------------------------------------------------------------
@njit(cache=True)
def _st_ai_core(h, l, c, atr, factors, alpha, max_iter, frm):
    n = c.size
    m = factors.size
    hl2 = (h + l) / 2
    upper = np.full(m, hl2[0])
    lower = np.full(m, hl2[0])
    output = np.full(m, np.nan)
    perf = np.zeros(m)
    trend = np.zeros(m)
    tf_out = np.full(n, np.nan)
    os_out = np.zeros(n)
    target = np.nan
    up_ = hl2[0]
    lo_ = hl2[0]
    os_ = 0.0
    for i in range(n):
        cp = c[i - 1] if i > 0 else np.nan
        for k in range(m):
            up = hl2[i] + atr[i] * factors[k]
            dn = hl2[i] - atr[i] * factors[k]
            if c[i] > upper[k]:
                trend[k] = 1.0
            elif c[i] < lower[k]:
                trend[k] = 0.0
            if cp < upper[k]:
                upper[k] = up if up < upper[k] else upper[k]
                if np.isnan(up):
                    upper[k] = np.nan
            else:
                upper[k] = up
            if cp > lower[k]:
                lower[k] = dn if dn > lower[k] else lower[k]
                if np.isnan(dn):
                    lower[k] = np.nan
            else:
                lower[k] = dn
            diff = 0.0
            if not np.isnan(cp) and not np.isnan(output[k]):
                diff = np.sign(cp - output[k])
            dc = c[i] - cp if not np.isnan(cp) else 0.0
            perf[k] += 2.0 / (alpha + 1.0) * (dc * diff - perf[k])
            output[k] = lower[k] if trend[k] == 1.0 else upper[k]
        # k-средние по эффективности 9 линий
        srt = np.sort(perf)
        cen = np.empty(3)
        for q in range(3):
            pos = (q + 1) * 0.25 * (m - 1)
            lo_i = int(np.floor(pos))
            hi_i = min(lo_i + 1, m - 1)
            cen[q] = srt[lo_i] + (srt[hi_i] - srt[lo_i]) * (pos - lo_i)
        lab = np.zeros(m, np.int64)
        for it in range(max_iter + 1):
            for k in range(m):
                best = -1
                bd = np.inf
                for q in range(3):
                    dq = abs(perf[k] - cen[q])
                    if dq < bd:                 # NaN-центр (пустой кластер) не выбирается
                        bd = dq
                        best = q
                lab[k] = best
            nc = np.empty(3)
            for q in range(3):
                s = 0.0
                cnt = 0
                for k in range(m):
                    if lab[k] == q:
                        s += perf[k]
                        cnt += 1
                nc[q] = s / cnt if cnt else np.nan
            if nc[0] == cen[0] and nc[1] == cen[1] and nc[2] == cen[2]:
                break
            cen = nc
        s = 0.0
        cnt = 0
        for k in range(m):
            if lab[k] == frm:
                s += factors[k]
                cnt += 1
        if cnt:
            target = s / cnt
        tf_out[i] = target
        up = hl2[i] + atr[i] * target
        dn = hl2[i] - atr[i] * target
        if cp < up_:
            up_ = up if up < up_ else up_
            if np.isnan(up):
                up_ = np.nan
        else:
            up_ = up
        if cp > lo_:
            lo_ = dn if dn > lo_ else lo_
            if np.isnan(dn):
                lo_ = np.nan
        else:
            lo_ = dn
        if c[i] > up_:
            os_ = 1.0
        elif c[i] < lo_:
            os_ = 0.0
        os_out[i] = os_
    return os_out, tf_out


@register("supertrend_ai_luxalgo", title="SuperTrend AI (Clustering) [LuxAlgo]", author="LuxAlgo", url=TV + "wP7WWjLL/",
          boosts=30908, blocks=["ML", "VOLA"], tf="1D (график публикации), любой", warmup=150,
          signal="SuperTrend с множителем — средним лучшего кластера (k-средние по эффективности 9 линий 1…5):"
                 " os 0→1 — buy, 1→0 — sell", repaint="нет (кластеризация — на последних 10 000 барах графика)")
def supertrend_ai_luxalgo(o, h, l, c, v, length=10, min_mult=1.0, max_mult=5.0, step=0.5, perf_alpha=10.0,
                          from_cluster="Best", max_iter=1000):
    """SuperTrend AI (Clustering) [LuxAlgo], https://www.tradingview.com/script/wP7WWjLL/.
    9 SuperTrend (множители 1…5 шаг 0,5) с эффективностью perf += α·((c − c[1])·sign(c[1] − output[1]) − perf),
    α = 2/(10 + 1); k-средние (3 кластера, старт — квартили) на каждом баре; итоговый множитель — среднее множителей
    лучшего кластера; итоговая линия: os = 1 при close > upper, 0 при close < lower."""
    h, l, c = P.f64(h), P.f64(l), P.f64(c)
    factors = np.array([min_mult + i * step for i in range(int((max_mult - min_mult) / step) + 1)])
    frm = {"Best": 2, "Average": 1, "Worst": 0}[from_cluster]
    os_, tf_ = _st_ai_core(h, l, c, P.atr(h, l, c, length), factors, float(perf_alpha), int(max_iter), frm)
    po = P.shift(os_)
    return dict(buy=_gt(os_, po), sell=_lt(os_, po), os=os_, factor=tf_)


# ---------------------------------------------------------------------------------------------------------------
# 16. Divergence for Many Indicators v4 [LonesomeTheBlue]
# ---------------------------------------------------------------------------------------------------------------
@njit(cache=True)
def _div_scan(src, close, pos, vals, prd, maxpp, maxbars, positive):
    """Регулярная дивергенция на баре b: прошлые пивоты (позиции подтверждения pos[b, x], значения vals[b, x],
    новые слева) против бара b − 1 (startpoint = 1). Возвращает длину до пивота или 0."""
    n = src.size
    out = np.zeros(n, np.int64)
    for b in range(1, n):
        if positive:
            if not (src[b] > src[b - 1] or close[b] > close[b - 1]):
                continue
        else:
            if not (src[b] < src[b - 1] or close[b] < close[b - 1]):
                continue
        for x in range(maxpp):
            p = pos[b, x]
            if p == 0:
                break
            ln = b - p + prd
            if ln > maxbars:
                break
            if ln <= 5 or b - ln < 0:
                continue
            s1 = src[b - 1]
            sl = src[b - ln]
            if positive:
                cond = s1 > sl and close[b - 1] < vals[b, x]
            else:
                cond = s1 < sl and close[b - 1] > vals[b, x]
            if not cond:
                continue
            slope1 = (s1 - sl) / (ln - 1)
            vl1 = s1 - slope1
            slope2 = (close[b - 1] - close[b - ln]) / (ln - 1)
            vl2 = close[b - 1] - slope2
            arrived = True
            for y in range(2, ln):
                if positive:
                    if src[b - y] < vl1 or close[b - y] < vl2:
                        arrived = False
                        break
                else:
                    if src[b - y] > vl1 or close[b - y] > vl2:
                        arrived = False
                        break
                vl1 -= slope1
                vl2 -= slope2
            if arrived:
                out[b] = ln
                break
    return out


def _pivot_book(piv, maxsize=20):
    """Состояние массивов пивотов скрипта на каждом баре: позиции (бар подтверждения) и значения, новые первыми."""
    n = len(piv)
    pos = np.zeros((n, maxsize), np.int64)
    vals = np.zeros((n, maxsize))
    cp = np.zeros(maxsize, np.int64)
    cv = np.zeros(maxsize)
    for b in range(n):
        if not np.isnan(piv[b]) and piv[b] != 0:
            cp = np.r_[b, cp[:-1]]
            cv = np.r_[piv[b], cv[:-1]]
        pos[b] = cp
        vals[b] = cv
    return pos, vals


@register("divergence_many_v4", title="Divergence for Many Indicators v4", author="LonesomeTheBlue",
          url=TV + "n8AGnIZd/", boosts=30767, blocks=["OSC", "VOL", "STRUCT"], tf="1h (график публикации), любой",
          warmup=150,
          signal="регулярная бычья дивергенция хотя бы у одного из 10 индикаторов (MACD, гистограмма, RSI, Stoch, CCI,"
                 " Momentum, OBV, VWMACD, CMF, MFI) с одним из 10 последних пивотов (5/5 по close) — buy; медвежья — sell",
          repaint="сигнал — нет (проверка на текущем баре против прошлых пивотов); но скрипт стирает прежнюю метку,"
                  " если до нового пивота пришла новая дивергенция — на истории меток меньше, чем было в реальном времени")
def divergence_many_v4(o, h, l, c, v, prd=5, maxpp=10, maxbars=100, showlimit=1):
    """Divergence for Many Indicators v4 [LonesomeTheBlue], https://www.tradingview.com/script/n8AGnIZd/.
    Для каждого индикатора: если src > src[1] или close > close[1], по 10 последним пивот-минимумам close (5/5)
    в пределах 100 баров ищется пивот, где src[1] > src[len], close[1] < значения пивота и обе «виртуальные линии»
    (по src и close) не пересекаются барами между — бычья регулярная дивергенция; медвежья — зеркально.
    Сигнал — число индикаторов с дивергенцией ≥ 1 (alertcondition Positive/Negative Regular Divergence Detected)."""
    o, h, l, c, v = (P.f64(x) for x in (o, h, l, c, v))
    ema12, ema26 = P.ema(c, 12), P.ema(c, 26)
    macd = ema12 - ema26
    hist = macd - P.ema(macd, 9)
    ch = P.change(c)
    obv = np.cumsum(np.nan_to_num(np.sign(ch) * v))
    with np.errstate(divide="ignore", invalid="ignore"):
        cmfm = ((c - l) - (h - c)) / (h - l)
    cmf = P.sma(cmfm * v, 21) / P.sma(v, 21)
    inds = [macd, hist, P.rsi(c, 14), P.sma(P.stoch(c, h, l, 14), 3), P.cci(c, 10), c - P.shift(c, 10), obv,
            P.vwma(c, v, 12) - P.vwma(c, v, 26), cmf, P.mfi(c, v, 14)]
    plp, plv = _pivot_book(P.pivotlow(c, prd, prd))
    php, phv = _pivot_book(P.pivothigh(c, prd, prd))
    pos_cnt = np.zeros(len(c), np.int64)
    neg_cnt = np.zeros(len(c), np.int64)
    for x in inds:
        xs = np.where(np.isnan(x), np.nan, x)
        pos_cnt += _div_scan(xs, c, plp, plv, prd, maxpp, maxbars, True) > 0
        neg_cnt += _div_scan(xs, c, php, phv, prd, maxpp, maxbars, False) > 0
    tot = pos_cnt + neg_cnt
    ok = tot >= showlimit
    return dict(buy=(pos_cnt > 0) & ok, sell=(neg_cnt > 0) & ok, n_pos=pos_cnt, n_neg=neg_cnt)


# ---------------------------------------------------------------------------------------------------------------
# 17. Chandelier Exit [everget]
# ---------------------------------------------------------------------------------------------------------------
@njit(cache=True)
def _ce_core(c, hi, lo, atr):
    n = c.size
    ls = np.full(n, np.nan)
    ss = np.full(n, np.nan)
    dr = np.ones(n)
    d = 1.0
    for i in range(n):
        x = hi[i] - atr[i]
        lsp = ls[i - 1] if (i > 0 and not np.isnan(ls[i - 1])) else x
        if i > 0 and c[i - 1] > lsp:
            x = x if x > lsp else lsp
        y = lo[i] + atr[i]
        ssp = ss[i - 1] if (i > 0 and not np.isnan(ss[i - 1])) else y
        if i > 0 and c[i - 1] < ssp:
            y = y if y < ssp else ssp
        ls[i] = x
        ss[i] = y
        if c[i] > ssp:
            d = 1.0
        elif c[i] < lsp:
            d = -1.0
        dr[i] = d
    return ls, ss, dr


@register("chandelier_everget", title="Chandelier Exit [everget]", author="everget", url=TV + "AqXxNS7j/",
          boosts=30389, blocks=["VOLA"], tf="1D (график публикации), любой", warmup=60,
          signal="смена направления: −1→1 buy, 1→−1 sell (метки Buy/Sell)", repaint="нет")
def chandelier_everget(o, h, l, c, v, length=22, mult=3.0, use_close=True):
    """Chandelier Exit [everget], https://www.tradingview.com/script/AqXxNS7j/.
    longStop = highest(c,22) − 3·atr(22), shortStop = lowest(c,22) + 3·atr(22) (useClose=true), с подтягиванием;
    dir = 1 при c > shortStop[1], −1 при c < longStop[1]."""
    h, l, c = P.f64(h), P.f64(l), P.f64(c)
    atr = mult * P.atr(h, l, c, length)
    hi = P.highest(c if use_close else h, length)
    lo = P.lowest(c if use_close else l, length)
    ls, ss, dr = _ce_core(c, hi, lo, atr)
    pd_ = P.shift(dr)
    return dict(buy=(dr == 1) & (pd_ == -1), sell=(dr == -1) & (pd_ == 1), long_stop=ls, short_stop=ss, dir=dr)


# ---------------------------------------------------------------------------------------------------------------
# 18. CM Sling Shot System [ChrisMoody]
# ---------------------------------------------------------------------------------------------------------------
@register("slingshot_cm", title="CM Sling Shot System", author="ChrisMoody", url=TV + "GE7tSQK1/", boosts=30009,
          blocks=["MA"], tf="1D (график публикации)", warmup=300,
          signal="«консервативный вход»: EMA38 > EMA62, close[1] < EMA38 и close > EMA38 — buy; зеркально sell",
          repaint="нет")
def slingshot_cm(o, h, l, c, v, fast=38, slow=62):
    """CM_SlingShotSystem [ChrisMoody], https://www.tradingview.com/script/GE7tSQK1/.
    Тренд — EMA 38 против EMA 62; вход после отката: close возвращается за быструю EMA по тренду (стрелки)."""
    c = P.f64(c)
    ef, es = P.ema(c, fast), P.ema(c, slow)
    pc = P.shift(c)
    buy = _gt(ef, es) & _lt(pc, ef) & _gt(c, ef)
    sell = _lt(ef, es) & _gt(pc, ef) & _lt(c, ef)
    return dict(buy=buy, sell=sell, ema_fast=ef, ema_slow=es)


# ---------------------------------------------------------------------------------------------------------------
# 19. AlphaTrend [KivancOzbilgic]
# ---------------------------------------------------------------------------------------------------------------
@njit(cache=True)
def _alpha_core(cond, upT, downT):
    n = cond.size
    at = np.full(n, np.nan)
    for i in range(n):
        p = at[i - 1] if (i > 0 and not np.isnan(at[i - 1])) else 0.0
        if cond[i]:
            at[i] = p if upT[i] < p else upT[i]
        else:
            at[i] = p if downT[i] > p else downT[i]
    return at


@register("alphatrend_kivanc", title="AlphaTrend", author="KivancOzbilgic", url=TV + "o50NYLAZ/", boosts=29974,
          blocks=["VOLA", "VOL"], tf="1D (график публикации), любой", warmup=60,
          signal="crossover(AT, AT[2]) — buy, crossunder — sell, с чередованием (метки BUY/SELL)",
          repaint="нет на закрытом баре (есть «подтверждённый» вариант на баре позже)")
def alphatrend_kivanc(o, h, l, c, v, coeff=1.0, ap=14, novolume=False):
    """AlphaTrend [KivancOzbilgic], https://www.tradingview.com/script/o50NYLAZ/.
    ATR = sma(tr, 14); при MFI(hlc3, 14) ≥ 50 линия = max(low − ATR, AT[1]), иначе min(high + ATR, AT[1]);
    сигнал — пересечение AT своей копией двухбарной давности, повторы в одну сторону отсекаются."""
    h, l, c, v = P.f64(h), P.f64(l), P.f64(c), P.f64(v)
    atr = P.sma(P.tr(h, l, c, False), ap)
    upT, downT = l - atr * coeff, h + atr * coeff
    osc = P.rsi(c, ap) if novolume else P.mfi((h + l + c) / 3, v, ap)
    with np.errstate(invalid="ignore"):
        up_mode = np.asarray(osc >= 50, bool)
    at = _alpha_core(up_mode, upT, downT)
    at2 = P.shift(at, 2)
    bk, sk = P.crossover(at, at2), P.crossunder(at, at2)
    K1, K2 = P.barssince(bk), P.barssince(sk)
    O1, O2 = P.barssince(P.shift(bk.astype(float)) == 1), P.barssince(P.shift(sk.astype(float)) == 1)
    return dict(buy=bk & _gt(O1, K2), sell=sk & _gt(O2, K1), at=at)


# ---------------------------------------------------------------------------------------------------------------
# 20. Pivot Point SuperTrend [LonesomeTheBlue]
# ---------------------------------------------------------------------------------------------------------------
@njit(cache=True)
def _ppst_core(c, ph, pl, atr, factor):
    n = c.size
    trend = np.zeros(n)
    tup_a = np.full(n, np.nan)
    tdn_a = np.full(n, np.nan)
    center = np.nan
    tr_ = 1.0
    for i in range(n):
        lp = np.nan
        if not np.isnan(ph[i]) and ph[i] != 0:
            lp = ph[i]
        elif not np.isnan(pl[i]) and pl[i] != 0:
            lp = pl[i]
        if not np.isnan(lp):
            center = lp if np.isnan(center) else (center * 2 + lp) / 3
        up = center - factor * atr[i]
        dn = center + factor * atr[i]
        tp = tup_a[i - 1] if i > 0 else np.nan
        dp = tdn_a[i - 1] if i > 0 else np.nan
        cp = c[i - 1] if i > 0 else np.nan
        if cp > tp:
            tup_a[i] = up if up > tp else tp
            if np.isnan(up):
                tup_a[i] = np.nan
        else:
            tup_a[i] = up
        if cp < dp:
            tdn_a[i] = dn if dn < dp else dp
            if np.isnan(dn):
                tdn_a[i] = np.nan
        else:
            tdn_a[i] = dn
        if c[i] > dp:
            tr_ = 1.0
        elif c[i] < tp:
            tr_ = -1.0
        trend[i] = tr_
    return trend


@register("pp_supertrend", title="Pivot Point Supertrend", author="LonesomeTheBlue", url=TV + "L0AIiLvH/",
          boosts=29804, blocks=["STRUCT", "VOLA"], tf="5m (график публикации), любой", warmup=60,
          signal="смена тренда: −1→1 buy, 1→−1 sell", repaint="нет: центр — по пивотам 2/2, подтверждённым через 2 бара")
def pp_supertrend(o, h, l, c, v, prd=2, factor=3.0, pd=10):
    """Pivot Point SuperTrend [LonesomeTheBlue], https://www.tradingview.com/script/L0AIiLvH/.
    center = (2·center + пивот)/3 по пивотам 2/2 (high/low); полосы center ∓ 3·atr(10) с подтягиванием;
    trend = 1 при close > TDown[1], −1 при close < TUp[1]."""
    h, l, c = P.f64(h), P.f64(l), P.f64(c)
    tr_ = _ppst_core(c, P.pivothigh(h, prd, prd), P.pivotlow(l, prd, prd), P.atr(h, l, c, pd), float(factor))
    pt = P.shift(tr_)
    return dict(buy=(tr_ == 1) & (pt == -1), sell=(tr_ == -1) & (pt == 1), trend=tr_)


# ---------------------------------------------------------------------------------------------------------------
# 21. Candlestick Patterns Identified [repo32] — поглощения
# ---------------------------------------------------------------------------------------------------------------
@register("engulfing_repo32", title="Candlestick Patterns Identified (updated 3/11/15)", author="repo32",
          url=TV + "vcsWo8mh/", boosts=35112, blocks=["PAT"], tf="1D (по описанию: «лучше видны на дневках»)",
          warmup=10,
          signal="бычье поглощение после снижения (open[5] > open) — buy; медвежье после роста (open[5] < open) — sell",
          repaint="нет")
def engulfing_repo32(o, h, l, c, v, trend=5):
    """Candlestick Patterns Identified [repo32], https://www.tradingview.com/script/vcsWo8mh/ — Bullish/Bearish Engulfing.
    bullEng: open[1] > close[1], close > open, close ≥ open[1], close[1] ≥ open, тело больше прошлого, open[5] > open;
    bearEng — зеркально (open[5] < open). Остальные 13 фигур скрипта (доджи, молоты, звёзды…) не берутся."""
    o, c = P.f64(o), P.f64(c)
    o1, c1, ot = P.shift(o), P.shift(c), P.shift(o, trend)
    with np.errstate(invalid="ignore"):
        bull = (o1 > c1) & (c > o) & (c >= o1) & (c1 >= o) & (c - o > o1 - c1) & (ot > o)
        bear = (c1 > o1) & (o > c) & (o >= c1) & (o1 >= c) & (o - c > c1 - o1) & (ot < o)
    return dict(buy=np.asarray(bull, bool), sell=np.asarray(bear, bool))


# ---------------------------------------------------------------------------------------------------------------
# 22. Breakout Finder [LonesomeTheBlue]
# ---------------------------------------------------------------------------------------------------------------
def breakout_finder_core(o, h, l, c, prd, bo_len, cw, mintest):
    n = len(c)
    buy = np.zeros(n, bool)
    sell = np.zeros(n, bool)
    ph = P.pivothigh(h, prd, prd)
    pl = P.pivotlow(l, prd, prd)
    hg = P.shift(P.highest(h, prd), 1)
    lw = P.shift(P.lowest(l, prd), 1)
    phv, phl, plv, pll = [], [], [], []
    hh = np.full(n, np.nan)
    ll = np.full(n, np.nan)
    for i in range(n):                      # highest/lowest за min(bar_index, 300) баров
        L = max(min(i, 300), 1)
        hh[i] = h[i - L + 1:i + 1].max()
        ll[i] = l[i - L + 1:i + 1].min()
    for i in range(n):
        chw = (hh[i] - ll[i]) * cw
        if not np.isnan(ph[i]) and ph[i] != 0:
            phv.insert(0, ph[i])
            phl.insert(0, i - prd)
            if len(phv) > 1:
                for x in range(len(phl) - 1, 0, -1):
                    if i - phl[x] > bo_len:
                        phl.pop()
                        phv.pop()
        if not np.isnan(pl[i]) and pl[i] != 0:
            plv.insert(0, pl[i])
            pll.insert(0, i - prd)
            if len(plv) > 1:
                for x in range(len(pll) - 1, 0, -1):
                    if i - pll[x] > bo_len:
                        pll.pop()
                        plv.pop()
        if len(phv) >= mintest and c[i] > o[i] and c[i] > hg[i]:
            bomax = phv[0]
            xx = 0
            for x in range(len(phv)):
                if phv[x] >= c[i]:
                    break
                xx = x
                bomax = max(bomax, phv[x])
            num = 0
            if xx >= mintest and o[i] <= bomax:
                for x in range(xx + 1):
                    if bomax - chw <= phv[x] <= bomax:
                        num += 1
                if not (num < mintest or hg[i] >= bomax):
                    buy[i] = num >= mintest
        if len(plv) >= mintest and c[i] < o[i] and c[i] < lw[i]:
            bomin = plv[0]
            xx = 0
            for x in range(len(plv)):
                if plv[x] <= c[i]:
                    break
                xx = x
                bomin = min(bomin, plv[x])
            num = 0
            if xx >= mintest and o[i] >= bomin:
                for x in range(xx + 1):
                    if bomin <= plv[x] <= bomin + chw:
                        num += 1
                if not (num < mintest or lw[i] <= bomin):
                    sell[i] = num >= mintest
    return buy, sell


@register("breakout_finder", title="Breakout Finder", author="LonesomeTheBlue", url=TV + "EvkXjgyw/", boosts=27841,
          blocks=["STRUCT"], tf="5m (график публикации), любой", warmup=320,
          signal="закрытие бычьей свечи выше зоны из ≥ 2 пивот-максимумов (5/5) шириной 3% размаха 300 баров — buy;"
                 " зеркально sell", repaint="нет: пивоты подтверждены через 5 баров")
def breakout_finder(o, h, l, c, v, prd=5, bo_len=200, cwidthu=3.0, mintest=2):
    """Breakout Finder [LonesomeTheBlue], https://www.tradingview.com/script/EvkXjgyw/.
    Пивоты за 200 баров; пробой: close > open, close > highest(5)[1], ≥ 2 пивота в полосе [bomax − 3%·размах, bomax],
    open ≤ bomax и highest(5)[1] < bomax."""
    o, h, l, c = (P.f64(x) for x in (o, h, l, c))
    buy, sell = breakout_finder_core(o, h, l, c, int(prd), int(bo_len), cwidthu / 100.0, int(mintest))
    return dict(buy=buy, sell=sell)


# ---------------------------------------------------------------------------------------------------------------
# 23. Volume Flow Indicator [LazyBear]
# ---------------------------------------------------------------------------------------------------------------
@register("vfi_lb", title="Volume Flow Indicator [LazyBear]", author="LazyBear", url=TV + "MhlDpfdS/", boosts=27345,
          blocks=["VOL"], tf="1h (график публикации)", warmup=270,
          signal="VFI пересекает 0 вверх — buy, вниз — sell (правило Катсаноса из описания)", repaint="нет")
def vfi_lb(o, h, l, c, v, length=130, coef=0.2, vcoef=2.5):
    """Volume Flow Indicator [LazyBear] (Katsanos), https://www.tradingview.com/script/MhlDpfdS/.
    inter = Δlog(hlc3); cutoff = 0,2·stdev(inter,30)·close; vave = sma(v,130)[1]; vc = min(v, 2,5·vave);
    vcp = ±vc при |Δhlc3| > cutoff; VFI = Σ_{130} vcp / vave."""
    h, l, c, v = P.f64(h), P.f64(l), P.f64(c), P.f64(v)
    tp = (h + l + c) / 3
    inter = np.log(tp) - np.log(P.shift(tp))
    cutoff = coef * P.stdev(inter, 30) * c
    vave = P.shift(P.sma(v, length), 1)
    vc = np.where(v < vave * vcoef, v, vave * vcoef)
    mf = tp - P.shift(tp)
    vcp = np.where(_gt(mf, cutoff), vc, np.where(_lt(mf, -cutoff), -vc, 0.0))
    vcp[np.isnan(cutoff) | np.isnan(vave)] = np.nan
    vfi = P.ssum(vcp, length) / vave
    return dict(buy=P.crossover(vfi, 0), sell=P.crossunder(vfi, 0), vfi=vfi)


# ---------------------------------------------------------------------------------------------------------------
# 24. CM RSI-2 Strategy Lower Indicator [ChrisMoody] (Коннорс)
# ---------------------------------------------------------------------------------------------------------------
@register("rsi2_cm", title="CM RSI-2 Strategy Lower Indicator", author="ChrisMoody", url=TV + "xOm7jSPf/",
          boosts=24692, blocks=["OSC", "MA"], tf="1D (по описанию)", warmup=220,
          signal="RSI(2) < 10, close > SMA200 и close < SMA5 (зелёная линия) — buy; RSI(2) > 90, close < SMA200,"
                 " close > SMA5 — sell; первый бар серии", repaint="нет")
def rsi2_cm(o, h, l, c, v):
    """_CM_RSI_2_Strat_Low [ChrisMoody], https://www.tradingview.com/script/xOm7jSPf/ — RSI-2 Ларри Коннорса."""
    c = P.f64(c)
    ch = P.change(c)
    up = P.rma(np.where(np.isnan(ch), np.nan, np.maximum(ch, 0)), 2)
    dn = P.rma(np.where(np.isnan(ch), np.nan, -np.minimum(ch, 0)), 2)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.where(dn == 0, 100.0, np.where(up == 0, 0.0, 100 - 100 / (1 + up / dn)))
    r[np.isnan(up) | np.isnan(dn)] = np.nan
    ma5, ma200 = P.sma(c, 5), P.sma(c, 200)
    g = _gt(c, ma200) & _lt(c, ma5) & _lt(r, 10)
    rd = _lt(c, ma200) & _gt(c, ma5) & _gt(r, 90)
    return dict(buy=_first(g), sell=_first(rd), rsi=r)


# ---------------------------------------------------------------------------------------------------------------
# 25. Hull Suite [InSilico]
# ---------------------------------------------------------------------------------------------------------------
@register("hull_suite", title="Hull Suite", author="InSilico", url=TV + "hg92pFwS/", boosts=22883, blocks=["MA"],
          tf="1h (график публикации); длина 55 — «для входов в свинг»", warmup=120,
          signal="HMA(55) пересекает своё значение 2 бара назад вверх — buy («Hull trending up»), вниз — sell",
          repaint="нет на своём таймфрейме (старший таймфрейм — security без смещения, перерисовка внутри бара)")
def hull_suite(o, h, l, c, v, length=55):
    """Hull Suite [InSilico], https://www.tradingview.com/script/hg92pFwS/.
    HMA = wma(2·wma(c, 27) − wma(c, 55), 7); сигнал — crossover(HULL, HULL[2]) / crossover(HULL[2], HULL)."""
    hull = P.hma(P.f64(c), length)
    h2 = P.shift(hull, 2)
    return dict(buy=P.crossover(hull, h2), sell=P.crossover(h2, hull), hull=hull)


# ---------------------------------------------------------------------------------------------------------------
# 26. Turtle Trade Channels Indicator [KivancOzbilgic]
# ---------------------------------------------------------------------------------------------------------------
@register("turtle_kivanc", title="Turtle Trade Channels Indicator TUTCI", author="KivancOzbilgic",
          url=TV + "pB5nv16J/", boosts=20313, blocks=["STRUCT"], tf="1D (по описанию: «20-day breakout»)", warmup=40,
          signal="high достиг максимума 20 баров (Long Entry, первый после выхода по минимуму 10) — buy;"
                 " low — минимума 20 (Short Entry) — sell", repaint="нет")
def turtle_kivanc(o, h, l, c, v, length=20, len2=10):
    """Turtle Trade Channels [KivancOzbilgic], https://www.tradingview.com/script/pB5nv16J/ — каналы Дончиана 20/10.
    buySignal: high == highest(h,20)[1] или crossover(high, highest(h,20)[1]); метка Long Entry — только если
    после прошлого входа был выход (low ≤ lowest(l,10)[1])."""
    h, l = P.f64(h), P.f64(l)
    upper, lower = P.highest(h, length), P.lowest(l, length)
    sup, sdown = P.highest(h, len2), P.lowest(l, len2)
    u1, l1, su1, sd1 = P.shift(upper), P.shift(lower), P.shift(sup), P.shift(sdown)
    bs = (h == u1) | P.crossover(h, u1)
    ss = (l == l1) | P.crossover(l1, l)
    bx = (l == sd1) | P.crossover(sd1, l)
    sx = (h == su1) | P.crossover(h, su1)
    O1, O2, O3, O4 = (P.barssince(x) for x in (bs, ss, bx, sx))
    return dict(buy=bs & _lt(O3, P.shift(O1)), sell=ss & _lt(O4, P.shift(O2)))


# ---------------------------------------------------------------------------------------------------------------
# Стратегии из топа
# ---------------------------------------------------------------------------------------------------------------
@register("bb_rsi_chartart", title="Bollinger + RSI, Double Strategy (by ChartArt) v1.1", author="ChartArt",
          url=TV + "uCV8I4xA/", boosts=49517, blocks=["VOLA", "OSC"], tf="1h (график публикации)", warmup=260,
          signal="strategy.entry: RSI(6) пересекает 50 вверх и close пересекает нижнюю BB(200, 2) вверх на одном баре"
                 " — buy (стоп-заявка по BBlower); зеркально sell", repaint="нет", kind="strategy")
def bb_rsi_chartart(o, h, l, c, v, rsi_len=6, bb_len=200, bb_mult=2.0):
    """Bollinger + RSI, Double Strategy v1.1 [ChartArt], https://www.tradingview.com/script/uCV8I4xA/."""
    c = P.f64(c)
    r = P.rsi(c, rsi_len)
    basis = P.sma(c, bb_len)
    dev = bb_mult * P.stdev(c, bb_len)
    return dict(buy=P.crossover(r, 50) & P.crossover(c, basis - dev),
                sell=P.crossunder(r, 50) & P.crossunder(c, basis + dev))


@register("macd_sma200_chartart", title="MACD + SMA 200 Strategy (by ChartArt)", author="ChartArt",
          url=TV + "yMCa3XZD/", boosts=32131, blocks=["MA", "OSC"], tf="1D (график публикации)", warmup=260,
          signal="гистограмма MACD(SMA 12/26/9) пересекает 0 вверх, MACD > 0, SMA12 > SMA26, close[26] > SMA200 — buy;"
                 " зеркально sell", repaint="нет", kind="strategy")
def macd_sma200_chartart(o, h, l, c, v, fast=12, slow=26, signal=9, very_slow=200):
    """MACD + SMA 200 Strategy [ChartArt], https://www.tradingview.com/script/yMCa3XZD/ (MACD на простых средних)."""
    c = P.f64(c)
    f, s, vs = P.sma(c, fast), P.sma(c, slow), P.sma(c, very_slow)
    m = f - s
    hist = m - P.sma(m, signal)
    c26 = P.shift(c, slow)
    buy = P.crossover(hist, 0) & _gt(m, 0) & _gt(f, s) & _gt(c26, vs)
    sell = P.crossunder(hist, 0) & _lt(m, 0) & _lt(f, s) & _lt(c26, vs)
    return dict(buy=buy, sell=sell)


@register("ao_stoch_rsi_serdar", title="Buy&Sell Strategy depends on AO+Stoch+RSI+ATR by SerdarYILMAZ",
          author="SerdarYILMAZ", url=TV + "RpYoQCVJ/", boosts=14568, blocks=["OSC"], tf="1h (график публикации)",
          warmup=60, signal="Stoch %K(14,3) < 20, RSI(10) < 30 и AO растёт — buy; %K > 80, RSI > 70, AO падает — sell;"
                            " первый бар серии", repaint="нет", kind="strategy")
def ao_stoch_rsi_serdar(o, h, l, c, v):
    """Buy&Sell Strategy AO+Stoch+RSI+ATR [SerdarYILMAZ], https://www.tradingview.com/script/RpYoQCVJ/."""
    h, l, c = P.f64(h), P.f64(l), P.f64(c)
    hl2 = (h + l) / 2
    ao = (P.sma(hl2, 5) - P.sma(hl2, 34)) * 1000
    k = P.sma(P.stoch(c, h, l, 14), 3)
    r = P.rsi(c, 10)
    pa = P.shift(ao)
    lc = _lt(k, 20) & _lt(r, 30) & _gt(ao, pa)
    sc = _gt(k, 80) & _gt(r, 70) & _lt(ao, pa)
    return dict(buy=_first(lc), sell=_first(sc))
