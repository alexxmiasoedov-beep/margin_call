"""s187 — проверка повторённых индикаторов (без доходов): формулы, отсутствие заглядывания вперёд, частоты сигналов.

Запуск — в окружении с эталонными библиотеками и numba (/home/user/mc_data/s187/venv: TA-Lib 0.8, pandas-ta 0.4, numba):
  venv/bin/python check.py ref        — функции pine.py против TA-Lib / pandas-ta на часовых свечах 3 монет;
  venv/bin/python check.py sem        — семантика Pine на искусственных рядах (пивоты, пересечения, тренды);
  venv/bin/python check.py look       — «нет заглядывания вперёд»: сигналы на барах ≤ i не меняются при обрезке после i;
  venv/bin/python check.py freq       — частоты сигналов на 1h и 4h по ликвидным альтам трёх периодов
                                         (+ сигналы → /home/user/mc_data/s187/signals_<период>_<tf>.pkl);
  venv/bin/python check.py all        — всё подряд. Лог — check.log рядом.
Частота: сигнал считается, если закрытие бара попало в неделю ликвидности монеты [d0, d0 + 7 сут) внутри периода и
у монеты до начала недели было не меньше баров, чем прогрев индикатора (warmup в реестре)."""
import os
import pickle
import sys
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import indicators as I  # noqa: E402
import pine as P  # noqa: E402

D = "/home/user/mc_data/s187"
PERS = ["2020–2022", "2022–2024", "2024–2026"]
TFS = {"1h": 3600, "4h": 14400}
WEEK = 7 * 86400


def log(*a):
    print(*a, flush=True)


def load_bars(per):
    return pickle.load(open(f"{D}/bars_{per}.pkl", "rb"))


def arrs(b):
    return tuple(np.asarray(b[k], np.float64) for k in ("o", "h", "l", "c", "v"))


# ---------------------------------------------------------------------------------------------------------------
# 1. Формулы против эталонов
# ---------------------------------------------------------------------------------------------------------------
def _cmp(name, a, b, skip, tol=1e-6, rel=True):
    a, b = np.asarray(a, float)[skip:], np.asarray(b, float)[skip:]
    m = ~np.isnan(a) & ~np.isnan(b)
    if m.sum() == 0:
        log(f"  {name:38s} нет общих значений")
        return False
    d = np.abs(a[m] - b[m])
    if rel:                                  # относительное отклонение; у значений около нуля — к 1e-6
        d = d / np.maximum(np.abs(b[m]), 1e-6)
    nan_mis = int((np.isnan(a) != np.isnan(b)).sum())
    ok = d.max() <= tol
    log(f"  {name:38s} {'OK ' if ok else 'РАЗЛ'} max {'отн.' if rel else 'абс.'} откл. {d.max():.2e}, "
        f"точек {m.sum()}, расхождений NaN {nan_mis}")
    return ok


def ref():
    import pandas_ta as pta
    import talib
    log("== 1. Формулы pine.py против TA-Lib 0.8 и pandas-ta 0.4 (часовые свечи 2024–2026, после прогрева)")
    B = load_bars("2024–2026")["1h"]
    allok = True
    for s in ("SOL", "DOGE", "1000PEPE"):
        o, h, l, c, v = arrs(B[s])
        tp = (h + l + c) / 3
        log(f" {s}: {len(c)} баров")
        sk = 600
        chk = [
            ("sma(c,20)", P.sma(c, 20), talib.SMA(c, 20)),
            ("ema(c,26)", P.ema(c, 26), talib.EMA(c, 26)),
            ("wma(c,55)", P.wma(c, 55), talib.WMA(c, 55)),
            ("stdev(c,20) (смещённое)", P.stdev(c, 20), talib.STDDEV(c, 20, 1)),
            ("linreg(c,20,0)", P.linreg(c, 20), talib.LINEARREG(c, 20)),
            ("rsi(c,14)", P.rsi(c, 14), talib.RSI(c, 14)),
            ("rsi(c,2)", P.rsi(c, 2), talib.RSI(c, 2)),
            ("atr(10) (rma tr)", P.atr(h, l, c, 10), talib.ATR(h, l, c, 10)),
            ("highest(h,22)", P.highest(h, 22), talib.MAX(h, 22)),
            ("lowest(l,22)", P.lowest(l, 22), talib.MIN(l, 22)),
            ("sma(stoch(c,h,l,14),3)", P.sma(P.stoch(c, h, l, 14), 3),
             talib.STOCH(h, l, c, 14, 3, 0, 3, 0)[0]),
            ("cci(hlc3,20)", P.cci(tp, 20), talib.CCI(h, l, c, 20)),
            ("mfi(hlc3,v,14)", P.mfi(tp, v, 14), talib.MFI(h, l, c, v, 14)),
            ("macd 12/26", P.ema(c, 12) - P.ema(c, 26), talib.MACD(c, 12, 26, 9)[0]),
            ("macd signal ema9", P.ema(P.ema(c, 12) - P.ema(c, 26), 9), talib.MACD(c, 12, 26, 9)[1]),
            ("mom(c,10)", c - P.shift(c, 10), talib.MOM(c, 10)),
            ("hma(c,55)", P.hma(c, 55), pta.hma(pd.Series(c), 55).values),
            ("vwma(c,v,12)", P.vwma(c, v, 12), pta.vwma(pd.Series(c), pd.Series(v), 12).values),
            ("obv: приращения", np.diff(np.cumsum(np.nan_to_num(np.sign(P.change(c)) * v))),
             np.diff(talib.OBV(c, v))),
        ]
        p_, m_, adx_ = P.dmi(h, l, c, 14, 14)
        chk += [("+DI(14) rma", p_, talib.PLUS_DI(h, l, c, 14)), ("−DI(14) rma", m_, talib.MINUS_DI(h, l, c, 14)),
                ("ADX(14) rma", adx_, talib.ADX(h, l, c, 14))]
        r = I.adx_di(o, h, l, c, v)
        chk += [("ADX and DI: DI+ (суммы Уайлдера)", r["dip"], talib.PLUS_DI(h, l, c, 14)),
                ("ADX and DI: ADX = sma(DX,14)", r["adx"],
                 talib.SMA(talib.DX(h, l, c, 14), 14))]
        for nm, a, b in chk:
            allok &= _cmp(nm, a, b, sk)
        # индикаторы целиком
        sq = I.squeeze_lb(o, h, l, c, v)
        ref_sq = pta.squeeze(pd.Series(h), pd.Series(l), pd.Series(c), bb_length=20, bb_std=1.5, kc_length=20,
                             kc_scalar=1.5, lazybear=True, use_tr=True, mamode="sma")
        allok &= _cmp("Squeeze LB: val (pandas-ta lazybear)", sq["val"], ref_sq.iloc[:, 0].values, sk, tol=1e-6,
                      rel=False)
        # pandas-ta squeeze передаёт bb_std только в нижнюю полосу (верхняя — 2,0): sqzOn собираем из его bbands и kc
        bb = pta.bbands(pd.Series(c), 20, lower_std=1.5, upper_std=1.5, ddof=0, mamode="sma")
        kc = pta.kc(pd.Series(h), pd.Series(l), pd.Series(c), 20, 1.5, mamode="sma", tr=True)
        on_ref = (bb.iloc[:, 0].values > kc.iloc[:, 0].values) & (bb.iloc[:, 2].values < kc.iloc[:, 2].values)
        agree = (sq["sqz_on"][sk:] == on_ref[sk:]).mean()
        log(f"  {'Squeeze LB: sqzOn = pandas-ta bbands+kc':38s} {agree:.4%} баров")
        st = I.supertrend_kivanc(o, h, l, c, v)
        rst = pta.supertrend(pd.Series(h), pd.Series(l), pd.Series(c), length=10, multiplier=3.0)
        dcol = [x for x in rst.columns if x.startswith("SUPERTd")][0]
        agree = (st["trend"][sk:] == rst[dcol].values[sk:]).mean()
        log(f"  {'SuperTrend: тренд = pandas-ta':38s} {agree:.4%} баров (у pandas-ta классическая формула полос)")
        wt1, wt2 = I._wavetrend(h, l, c, 10, 21, 4)
        ap = pd.Series(tp)
        esa = ap.ewm(span=10, adjust=False).mean()
        dd = (ap - esa).abs().ewm(span=10, adjust=False).mean()
        w1 = ((ap - esa) / (0.015 * dd)).ewm(span=21, adjust=False).mean()
        allok &= _cmp("WaveTrend wt1 (pandas ewm, после прогрева)", wt1, w1.values, 3000, tol=1e-6, rel=False)
    log(f" итог: {'все формулы в допуске' if allok else 'ЕСТЬ РАСХОЖДЕНИЯ'}")
    return allok


# ---------------------------------------------------------------------------------------------------------------
# 2. Семантика Pine на искусственных рядах
# ---------------------------------------------------------------------------------------------------------------
def sem():
    log("== 2. Семантика Pine на искусственных рядах")
    ok = True

    def expect(name, cond):
        nonlocal ok
        ok &= bool(cond)
        log(f"  {'OK ' if cond else 'ОШИБКА'} {name}")

    x = np.array([1, 2, 3, 2, 1, 2, 3, 4, 3, 2.0])
    ph = P.pivothigh(x, 2, 2)
    expect("pivothigh(2,2): пивот бара 2 виден на баре 4, бара 7 — на баре 9",
           np.flatnonzero(~np.isnan(ph)).tolist() == [4, 9] and ph[4] == 3 and ph[9] == 4)
    pl = P.pivotlow(x, 2, 2)
    expect("pivotlow(2,2): пивот бара 4 виден на баре 6", np.flatnonzero(~np.isnan(pl)).tolist() == [6])
    flat = np.array([1, 2, 3, 3, 2, 1.0])
    expect("pivothigh при равных вершинах: строго выше слева, не ниже справа → левая из равных",
           np.flatnonzero(~np.isnan(P.pivothigh(flat, 2, 2))).tolist() == [4])
    expect("crossover(x, 2.5) — бары 2 и 6", np.flatnonzero(P.crossover(x, 2.5)).tolist() == [2, 6])
    expect("barssince: 0 на баре условия, NaN до первого",
           np.isnan(P.barssince(x > 2.5)[1]) and P.barssince(x > 2.5)[2] == 0 and P.barssince(x > 2.5)[5] == 3)
    expect("fixnan протягивает последнее значение",
           np.allclose(P.fixnan(np.array([np.nan, 1, np.nan, 3, np.nan]))[1:], [1, 1, 3, 3]))
    # тренды: рост, падение, рост, падение по 300 баров — у трендовых индикаторов продажа в начале падения
    # (у AlphaTrend первая продажа истории гасится фильтром чередования: barssince(na) > x ложно — как в Pine)
    t = np.arange(1200, dtype=float)
    c = np.r_[np.linspace(100, 200, 300), np.linspace(200, 100, 300), np.linspace(100, 200, 300),
              np.linspace(200, 100, 300)]
    c = c * (1 + 0.002 * np.sin(t * 1.7))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * 1.003
    l = np.minimum(o, c) * 0.997
    v = np.full(len(c), 1000.0)
    for nm in ("supertrend_kivanc", "ut_bot", "chandelier_everget", "hull_suite", "pp_supertrend",
               "ml_adaptive_st_algoalpha", "supertrend_ai_luxalgo", "alphatrend_kivanc", "turtle_kivanc"):
        r = I.REG[nm]["fn"](o, h, l, c, v)
        b = np.flatnonzero(r["buy"])
        s = np.flatnonzero(r["sell"])
        good = s[(s > 900) & (s < 1050)].size >= 1 and b[(b > 600) & (b < 800)].size >= 1
        expect(f"{nm}: «рост → падение → рост → падение»: покупка в начале 2-го роста, продажа в начале 2-го падения "
               f"(buy {b.tolist()[:6]}, sell {s.tolist()[:6]})", good)
    # SMC: подъём и спад (swing-пивоты), пилообразный рост (импульс +10, откат −4), затем слом вниз; swing 10
    seg = list(np.linspace(100, 130, 31)[1:]) + list(np.linspace(130, 90, 41)[1:])
    p0 = 90.0
    for k in range(12):
        seg += list(np.linspace(p0, p0 + 10, 8)[1:]) + list(np.linspace(p0 + 10, p0 + 6, 5)[1:])
        p0 += 6
    seg += list(np.linspace(p0, p0 - 40, 30)[1:])
    c = np.array([100.0] + seg)
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + 0.2
    l = np.minimum(o, c) - 0.2
    r = I.smc_luxalgo(o, h, l, c, np.ones(len(c)), swing_len=10, mode="internal_all")
    bos_up = np.flatnonzero(r["i_bos_buy"] | r["s_bos_buy"])
    choch_up = np.flatnonzero(r["i_choch_buy"] | r["s_choch_buy"])
    choch_dn = np.flatnonzero(r["i_choch_sell"] | r["s_choch_sell"])
    expect(f"SMC (swing 10): разворот вверх — бычий CHoCH {choch_up.tolist()[:3]}, в росте — бычьи BOS "
           f"({len(bos_up)}), слом вниз — медвежий CHoCH после бара {len(c) - 30} ({choch_dn.tolist()})",
           len(bos_up) >= 5 and choch_up.size >= 1 and choch_dn.size >= 1 and choch_dn.max() > len(c) - 30)
    # MSB: зигзаг с растущими вершинами и основаниями, затем пробой последнего основания вниз
    pts = [100, 120, 110, 135, 122, 150, 138, 165, 150, 120, 140]
    c = np.concatenate([np.linspace(pts[k], pts[k + 1], 15)[:-1] for k in range(len(pts) - 1)] + [[pts[-1]]])
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + 0.3
    l = np.minimum(o, c) - 0.3
    r = I.msb_emrekb(o, h, l, c, np.ones(len(c)))
    s_ = np.flatnonzero(r["sell"])
    expect(f"MSB: после растущего зигзага слом последнего основания (бар ~{14 * 9}) даёт одну продажу (бары {s_.tolist()})",
           s_[(s_ > 14 * 8) & (s_ <= 14 * 10)].size == 1)
    # Squeeze: тихий участок, затем расширение вверх — сигнал выхода из сжатия с val > 0
    rng = np.random.default_rng(1)
    c = np.r_[100 + np.cumsum(rng.normal(0, 0.05, 200)), 100 + np.cumsum(np.full(40, 0.8))]
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + 0.05
    l = np.minimum(o, c) - 0.05
    r = I.squeeze_lb(o, h, l, c, np.ones(len(c)))
    b = np.flatnonzero(r["buy"])
    expect(f"Squeeze: выход из сжатия вверх после бара 200 даёт buy (бары {b[b > 195].tolist()[:3]})",
           b[(b > 195) & (b < 225)].size >= 1)
    log(f" итог: {'семантика в порядке' if ok else 'ЕСТЬ ОШИБКИ'}")
    return ok


# ---------------------------------------------------------------------------------------------------------------
# 3. Нет заглядывания вперёд
# ---------------------------------------------------------------------------------------------------------------
def look(n_cuts=6, seed=7):
    log("== 3. Нет заглядывания вперёд: пересчёт на данных, обрезанных после бара i; сигналы на барах ≤ i совпадают")
    rng = np.random.default_rng(seed)
    allok = True
    bad = []
    for per, coins in (("2024–2026", ("SOL", "DOGE", "WLD")), ("2022–2024", ("SOL", "INJ"))):
        Bp = load_bars(per)
        for tf in TFS:
            for s in coins:
                if s not in Bp[tf]:
                    continue
                o, h, l, c, v = arrs(Bp[tf][s])
                n = len(c)
                full = {nm: m["fn"](o, h, l, c, v) for nm, m in I.REG.items()}
                cuts = sorted(rng.integers(int(n * 0.3), n - 5, n_cuts))
                for cut in cuts:
                    for nm, m in I.REG.items():
                        r = m["fn"](o[:cut + 1], h[:cut + 1], l[:cut + 1], c[:cut + 1], v[:cut + 1])
                        same = all(np.array_equal(full[nm][k][:cut + 1], r[k]) for k in ("buy", "sell"))
                        if not same:
                            allok = False
                            bad.append((per, tf, s, cut, nm))
    per_ind = {}
    for b in bad:
        per_ind[b[4]] = per_ind.get(b[4], 0) + 1
    log(f"  индикаторов {len(I.REG)}, рядов 10, обрезок на ряд {n_cuts}: "
        f"{'расхождений нет' if allok else 'РАСХОЖДЕНИЯ: ' + str(per_ind)}")
    return allok


# ---------------------------------------------------------------------------------------------------------------
# 4. Частоты сигналов
# ---------------------------------------------------------------------------------------------------------------
_G = {}


def _init(per, tf):
    _G["B"] = load_bars(per)
    _G["per"], _G["tf"] = per, tf


def _coin(s):
    B, tf = _G["B"], _G["tf"]
    b = B[tf][s]
    o, h, l, c, v = arrs(b)
    t_close = np.asarray(b["t"], np.int64) + TFS[tf]
    weeks = np.sort(B["liq"].loc[B["liq"].s == s, "d0"].values.astype(np.int64))
    wk = np.searchsorted(weeks, t_close, "right") - 1
    inw = (wk >= 0) & (t_close >= B["t0"]) & (t_close < B["t1"])
    inw[inw] = t_close[inw] < weeks[wk[inw]] + WEEK
    # бары монеты до начала каждой недели (прогрев)
    nbefore = np.searchsorted(t_close, weeks, "left")
    out = {}
    for nm, m in I.REG.items():
        r = m["fn"](o, h, l, c, v)
        elig_w = nbefore >= m["warmup"]
        el = inw.copy()
        el[inw] = elig_w[wk[inw]]
        nw = int(elig_w.sum())
        bi = np.flatnonzero(r["buy"] & el)
        si = np.flatnonzero(r["sell"] & el)
        out[nm] = (nw, t_close[bi], t_close[si])
    return s, out


def freq(pers=PERS, tfs=tuple(TFS)):
    log("== 4. Частоты сигналов (ликвидные альты: недели liq5 s183, без BTC и ETH)")
    rows = []
    for per in pers:
        for tf in tfs:
            t0 = time.time()
            B = load_bars(per)
            coins = sorted(set(B["liq"].s) & set(B[tf]))
            nweeks_all = B["liq"].d0.nunique()
            del B
            with Pool(4, initializer=_init, initargs=(per, tf)) as pool:
                res = pool.map(_coin, coins, chunksize=4)
            sig = {nm: [] for nm in I.REG}
            for s, out in res:
                for nm, (nw, tb, ts_) in out.items():
                    sig[nm].append((s, nw, tb, ts_))
            months = nweeks_all * 7 / 30.4
            store = {}
            for nm, lst in sig.items():
                cw = sum(x[1] for x in lst)
                nb = sum(len(x[2]) for x in lst)
                ns = sum(len(x[3]) for x in lst)
                cm = cw * 7 / 30.4
                rows.append(dict(ind=nm, per=per, tf=tf, coin_weeks=cw, buy_m=nb / months, sell_m=ns / months,
                                 buy_cm=nb / cm if cm else np.nan, sell_cm=ns / cm if cm else np.nan,
                                 coins_avg=cw / nweeks_all))
                store[nm] = {x[0]: (x[2].astype(np.int64), x[3].astype(np.int64)) for x in lst if len(x[2]) or len(x[3])}
            pickle.dump(store, open(f"{D}/signals_{per}_{tf}.pkl", "wb"), protocol=5)
            log(f"  {per} {tf}: монет {len(coins)}, недель {nweeks_all}, {time.time() - t0:.0f} с")
    F = pd.DataFrame(rows)
    F.to_pickle(f"{D}/freq.pkl")
    report_freq(F)
    return F


def report_freq(F=None):
    if F is None:
        F = pd.read_pickle(f"{D}/freq.pkl")
    pd.set_option("display.width", 250)
    log("\n  Сигналов в месяц на монету (buy / sell) и всего в месяц по ликвидным альтам, по периодам:")
    for tf in TFS:
        X = F[F.tf == tf]
        tab = []
        for nm in I.REG:
            r = {"индикатор": nm}
            for per in PERS:
                q = X[(X.ind == nm) & (X.per == per)]
                if len(q):
                    q = q.iloc[0]
                    r[f"{per} на монету"] = f"{q.buy_cm:.1f} / {q.sell_cm:.1f}"
                    r[f"{per} всего"] = f"{q.buy_m + q.sell_m:.0f}"
            tab.append(r)
        log(f"\n  {tf}:")
        log(pd.DataFrame(tab).to_string(index=False))
    cw = F.groupby(["per", "tf"]).coins_avg.max()
    log("\n  Средне ликвидных монет в неделю (с прогревом самого долгого индикатора меньше):")
    log(cw.to_string())


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("ref", "all"):
        ref()
    if what in ("sem", "all"):
        sem()
    if what in ("look", "all"):
        look()
    if what in ("freq", "all"):
        freq()
    if what == "report":
        report_freq()
