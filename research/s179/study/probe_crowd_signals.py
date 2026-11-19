"""s179 — частота сигналов «индикаторов толпы» по странам на криптоперпах Binance, три периода, без доходов.

Запуск: python3 -I probe_crowd_signals.py <папка данных>   (по умолчанию /home/user/mc_data)

Свечи: s117/k_2020.pkl (10.2020–09.2022), s117/k_oos.pkl (10.2022–09.2024), s2/k2y.pkl (10.2024–10.2026) —
15-мин свечи перпов {t, o, h, l, c, qv, tb, n}; дневки и 4-часовки собираются по UTC. Акции, металлы, индексы
и стейблкоины исключены (s12/perp_kind.pkl, ключ tradfi, и список s173). Вселенная — оборот перпа за день ≥ 5 млн $
(для 15-мин событий — за скользящие 24 ч).

Сигналы (дневки, если не сказано иное; «первый» — условие стало верным, накануне не было):
  США: RSI(14) снизу вверх через 70 и сверху вниз через 30; золотой крест SMA50/SMA200; цена закрылась выше SMA200;
       пробой 20-дневного максимума (Donchian); новый 52-недельный максимум закрытия (первый за 30 сут).
  Китай: MACD(12,26,9) DIF снизу вверх через DEA (金叉), он же выше нуля (零轴上金叉); KDJ(9,3,3) — J > 100 (超买),
       金叉 K/D при K < 20 (低位金叉); BOLL(20,2) закрытие выше верхней полосы; 均线多头排列 MA5 > MA10 > MA20 > MA60.
  Япония: 一目均衡表 — 三役好転 (転換線 > 基準線, цена выше облака, 遅行線 выше цены 26 дн. назад) и пробой облака;
       移動平均乖離率 (25 дн.) ≥ +20% и ≥ +30% (первый за 30 сут); RCI(9) снизу вверх через +80.
  Корея: 정배열 MA5 > MA20 > MA60 > MA120; 골든크로스 MA5/MA20 и MA20/MA60; 이격도 (20 дн.) ≥ 115.
  Binance по умолчанию: MA(7) снизу вверх через MA(25); цена выше MA(99) — на дневках и на 4 ч.
  4 ч: RSI(14) снизу вверх через 70; BOLL(20,2) выше верхней полосы.
  Круглые числа (15 мин, цена монеты в $ с учётом множителя 1000PEPE и т. п.): закрытие впервые за 30 сут выше
       круглого уровня {1, 2, 5}·10^k и {1…9}·10^k; первое за 30 сут касание уровня {1, 2, 5}·10^k с закрытием ниже
       (отказ); пробой вниз (закрытие впервые за 30 сут ниже уровня); пробой вверх с ростом свечи ≥ 3% («каскад»).
Для каждого сигнала — событий в месяц (среднее, медиана), монето-суток, разных дней с сигналом и доля событий в дни,
когда тот же сигнал дали ≥ 10 монет («широкий» день: рынок, а не монета).
"""
import os
import pickle
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"
NONCRYPTO = {"XAU", "XAG", "XPT", "XPD", "COPPER", "NATGAS", "CL", "BZ", "AAPL", "MSFT", "AMD", "QQQ", "SPY", "TSM",
             "BABA", "AMC", "CVX", "DIA", "AVGO", "QCOM", "ANET", "PAXG", "USDC", "FDUSD", "TUSD", "USDP", "BTCDOM",
             "DEFI", "BLUEBIRD", "HUT", "APLD", "GPRO", "SKHY", "OPENAI", "ANTHROPIC", "SPCX", "POPMART", "UNITREE",
             "MARSCOIN", "USAR", "SLX", "ESP", "USD1", "RLUSD", "XUSD", "BFUSD", "USDE"}
PERIODS = [("2020–2022", "s117/k_2020.pkl", "2020-10-01", "2022-10-01"),
           ("2022–2024", "s117/k_oos.pkl", "2022-10-01", "2024-10-01"),
           ("2024–2026", "s2/k2y.pkl", "2024-10-01", "2026-10-19")]
kind = pd.read_pickle(os.path.join(D, "s12/perp_kind.pkl"))
BAD = (set(kind.get("tradfi", set())) | NONCRYPTO) - {"BTC", "ETH"}
VMIN = 5e6


def mult(s):
    if s.startswith("1000000"):
        return 1e6
    if s.startswith("1000"):
        return 1e3
    if s.startswith("1M"):
        return 1e6
    return 1.0


def ts(x):
    return pd.Timestamp(x, tz="UTC").timestamp()


def agg(k, sec):
    """Свечи с объёмом → бары длины sec (UTC): t, o, h, l, c, qv; сплошная сетка с переносом цены."""
    t = np.asarray(k["t"], np.int64)
    qv = np.asarray(k["qv"], np.float64)
    live = np.flatnonzero(qv > 0)
    if len(live) < 10:
        return None
    a, b = live[0], live[-1] + 1
    t = t[a:b]; qv = qv[a:b]
    o = np.asarray(k["o"], np.float64)[a:b]; h = np.asarray(k["h"], np.float64)[a:b]
    l_ = np.asarray(k["l"], np.float64)[a:b]; c = np.asarray(k["c"], np.float64)[a:b]
    g = t // sec
    st = np.r_[0, np.flatnonzero(np.diff(g)) + 1]
    en = np.r_[st[1:], len(t)] - 1
    G = g[st]
    T = np.arange(G[0], G[-1] + 1)
    idx = G - G[0]
    out = {"T": T * sec}
    for nm, arr in (("o", o[st]), ("h", np.maximum.reduceat(h, st)), ("l", np.minimum.reduceat(l_, st)),
                    ("c", c[en]), ("qv", np.add.reduceat(qv, st))):
        z = np.full(len(T), np.nan); z[idx] = arr; out[nm] = z
    out["c"] = pd.Series(out["c"]).ffill().values
    for nm in ("o", "h", "l"):
        out[nm] = np.where(np.isnan(out[nm]), out["c"], out[nm])
    out["qv"] = np.nan_to_num(out["qv"])
    return out


def sma(x, n):
    return pd.Series(x).rolling(n, min_periods=n).mean().values


def ema(x, n):
    return pd.Series(x).ewm(span=n, adjust=False).mean().values


def rsi(c, n=14):
    d = np.diff(c, prepend=np.nan)
    up = pd.Series(np.where(d > 0, d, 0.0)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.where(d < 0, -d, 0.0)).ewm(alpha=1 / n, adjust=False).mean().values
    with np.errstate(divide="ignore", invalid="ignore"):
        r = 100 - 100 / (1 + up / dn)
    r[:n] = np.nan
    return r


def first(cond):
    """Условие стало верным в этот бар (накануне ложно)."""
    c = np.nan_to_num(cond.astype(float), nan=0.0) > 0
    p = np.r_[False, c[:-1]]
    return c & ~p


def first_in(cond, w):
    """Условие верно сейчас и не было верным ни разу за прошлые w баров."""
    c = np.nan_to_num(cond.astype(float), nan=0.0)
    prev = pd.Series(c).shift(1).rolling(w, min_periods=1).max().fillna(0).values
    return (c > 0) & (prev == 0)


def rci(c, n=9):
    out = np.full(len(c), np.nan)
    if len(c) < n:
        return out
    from numpy.lib.stride_tricks import sliding_window_view
    W = sliding_window_view(c, n)
    rank_p = W.argsort(axis=1).argsort(axis=1) + 1          # ранг цены (1 — самая низкая)
    rank_t = np.arange(1, n + 1)                            # ранг времени (1 — самый старый)
    d = rank_t[None, :] - rank_p
    out[n - 1:] = (1 - 6 * (d ** 2).sum(axis=1) / (n * (n * n - 1))) * 100
    return out


def daily_signals(x):
    c, h, l_, qv = x["c"], x["h"], x["l"], x["qv"]
    S = {}
    r14 = rsi(c)
    S["US RSI14 вверх через 70"] = (r14 > 70) & (np.r_[np.nan, r14[:-1]] <= 70)
    S["US RSI14 вниз через 30"] = (r14 < 30) & (np.r_[np.nan, r14[:-1]] >= 30)
    m50, m200 = sma(c, 50), sma(c, 200)
    S["US золотой крест SMA50/200"] = first(m50 > m200) & ~np.isnan(m200)
    S["US закрытие выше SMA200"] = first(c > m200) & ~np.isnan(m200)
    hh20 = pd.Series(h).shift(1).rolling(20, min_periods=20).max().values
    S["US пробой 20-дн. максимума"] = first(c > hh20)
    cmax365 = pd.Series(c).shift(1).rolling(365, min_periods=365).max().values
    S["US 52-нед. максимум (первый за 30 сут)"] = first_in(c > cmax365, 30)
    dif = ema(c, 12) - ema(c, 26); dea = pd.Series(dif).ewm(span=9, adjust=False).mean().values
    gx = first(dif > dea); gx[:35] = False
    S["CN MACD 金叉"] = gx
    S["CN MACD 金叉 выше нуля"] = gx & (dif > 0)
    ll9 = pd.Series(l_).rolling(9, min_periods=9).min().values; hh9 = pd.Series(h).rolling(9, min_periods=9).max().values
    with np.errstate(divide="ignore", invalid="ignore"):
        rsv = np.where(hh9 > ll9, (c - ll9) / (hh9 - ll9) * 100, 50.0)
    rsv = np.nan_to_num(rsv, nan=50.0)
    K = np.empty(len(c)); Dd = np.empty(len(c)); k_, d_ = 50.0, 50.0
    for i in range(len(c)):
        k_ = 2 / 3 * k_ + rsv[i] / 3; d_ = 2 / 3 * d_ + k_ / 3; K[i] = k_; Dd[i] = d_
    J = 3 * K - 2 * Dd
    jj = first(J > 100); jj[:12] = False
    S["CN KDJ J > 100"] = jj
    kg = first(K > Dd) & (K < 20); kg[:12] = False
    S["CN KDJ 低位金叉 (K < 20)"] = kg
    mb = sma(c, 20); sd = pd.Series(c).rolling(20, min_periods=20).std(ddof=0).values
    S["CN BOLL выше верхней полосы"] = first(c > mb + 2 * sd)
    m5, m10, m20, m60, m120 = sma(c, 5), sma(c, 10), sma(c, 20), sma(c, 60), sma(c, 120)
    S["CN 均线多头排列 5>10>20>60"] = first((m5 > m10) & (m10 > m20) & (m20 > m60))
    tenkan = (pd.Series(h).rolling(9).max() + pd.Series(l_).rolling(9).min()).values / 2
    kijun = (pd.Series(h).rolling(26).max() + pd.Series(l_).rolling(26).min()).values / 2
    sa = pd.Series((tenkan + kijun) / 2).shift(26).values
    sb = pd.Series((pd.Series(h).rolling(52).max() + pd.Series(l_).rolling(52).min()).values / 2).shift(26).values
    top = np.fmax(sa, sb)
    c26 = pd.Series(c).shift(26).values
    S["JP 三役好転"] = first((tenkan > kijun) & (c > top) & (c > c26)) & ~np.isnan(top)
    S["JP пробой облака вверх"] = first(c > top) & ~np.isnan(top)
    m25 = sma(c, 25)
    S["JP 乖離率 25 дн. ≥ +20%"] = first_in(c / m25 - 1 >= 0.20, 30)
    S["JP 乖離率 25 дн. ≥ +30%"] = first_in(c / m25 - 1 >= 0.30, 30)
    r9 = rci(c, 9)
    S["JP RCI(9) вверх через +80"] = (r9 > 80) & (np.r_[np.nan, r9[:-1]] <= 80)
    S["KR 정배열 5>20>60>120"] = first((m5 > m20) & (m20 > m60) & (m60 > m120))
    S["KR 골든크로스 MA5/MA20"] = first(m5 > m20) & ~np.isnan(m20)
    S["KR 골든크로스 MA20/MA60"] = first(m20 > m60) & ~np.isnan(m60)
    S["KR 이격도 20 дн. ≥ 115"] = first_in(c / m20 >= 1.15, 30)
    m7, m25b, m99 = sma(c, 7), sma(c, 25), sma(c, 99)
    S["BN дневка MA7 через MA25"] = first(m7 > m25b) & ~np.isnan(m25b)
    S["BN дневка цена выше MA99"] = first(c > m99) & ~np.isnan(m99)
    return S


def h4_signals(x):
    c = x["c"]
    S = {}
    r14 = rsi(c)
    S["4ч RSI14 вверх через 70"] = (r14 > 70) & (np.r_[np.nan, r14[:-1]] <= 70)
    mb = sma(c, 20); sd = pd.Series(c).rolling(20, min_periods=20).std(ddof=0).values
    S["4ч BOLL выше верхней полосы"] = first(c > mb + 2 * sd)
    m7, m25, m99 = sma(c, 7), sma(c, 25), sma(c, 99)
    S["BN 4ч MA7 через MA25"] = first(m7 > m25) & ~np.isnan(m25)
    S["BN 4ч цена выше MA99"] = first(c > m99) & ~np.isnan(m99)
    return S


def round_floor(p, steps):
    """Наибольший круглый уровень ≤ p: steps — мантиссы (например, (1, 2, 5))."""
    p = np.asarray(p, float)
    e = np.floor(np.log10(np.where(p > 0, p, np.nan)))
    m = p / 10 ** e
    st = np.asarray(steps, float)
    k = np.searchsorted(st, m + 1e-12, side="right") - 1
    return st[np.clip(k, 0, len(st) - 1)] * 10 ** e


def round_ceil(p, steps):
    p = np.asarray(p, float)
    e = np.floor(np.log10(np.where(p > 0, p, np.nan)))
    m = p / 10 ** e
    st = np.r_[np.asarray(steps, float), 10.0]
    k = np.searchsorted(st, m - 1e-12, side="left")
    return st[np.clip(k, 0, len(st) - 1)] * 10 ** e


def round_events(k, s):
    """15-мин события у круглых уровней цены монеты в $ (с поправкой на множитель)."""
    t = np.asarray(k["t"], np.int64)
    qv = np.asarray(k["qv"], np.float64)
    live = np.flatnonzero(qv > 0)
    if len(live) < 2880 * 2:
        return {}
    a, b = live[0], live[-1] + 1
    t = t[a:b]; qv = qv[a:b]
    mu = mult(s)
    c = np.asarray(k["c"], np.float64)[a:b] / mu
    h = np.asarray(k["h"], np.float64)[a:b] / mu
    o = np.asarray(k["o"], np.float64)[a:b] / mu
    v24 = pd.Series(qv).rolling(96, min_periods=96).sum().values
    W = 2880
    pmax_c = pd.Series(c).shift(1).rolling(W, min_periods=W).max().values
    pmin_c = pd.Series(c).shift(1).rolling(W, min_periods=W).min().values
    pmax_h = pd.Series(h).shift(1).rolling(W, min_periods=W).max().values
    ok = v24 >= VMIN
    ev = {}
    for nm, steps in (("{1,2,5}", (1, 2, 5)), ("{1…9}", (1, 2, 3, 4, 5, 6, 7, 8, 9))):
        rf = round_floor(c, steps)
        up = ok & (rf > pmax_c)
        ev[f"RN закрытие впервые за 30 сут выше уровня {nm}"] = t[up]
        if nm == "{1,2,5}":
            ret = c / np.where(o > 0, o, np.nan) - 1
            ev["RN пробой вверх {1,2,5} со свечой ≥ +3%"] = t[up & (ret >= 0.03)]
            rc = round_ceil(c, steps)
            dn = ok & (rc < pmin_c)
            ev["RN закрытие впервые за 30 сут ниже уровня {1,2,5}"] = t[dn]
            rh = round_floor(h, steps)
            rej = ok & (rh > pmax_h) & (c < rh) & (rh > pmax_c)
            ev["RN первое касание {1,2,5} с закрытием ниже (отказ)"] = t[rej]
    return ev


def summarize(name, rows, t0, t1, out):
    """rows: dict сигнал → список (монета, время)."""
    months = pd.period_range(pd.Timestamp(t0, unit="s"), pd.Timestamp(t1 - 1, unit="s"), freq="M")
    print(f"== {name}")
    print(f"  {'сигнал':52s} {'всего':>7s} {'в мес. ср.':>10s} {'медиана':>8s} {'дней/мес':>9s} {'доля в широкие дни':>18s} {'монет':>6s}")
    for sig, lst in rows.items():
        if not lst:
            print(f"  {sig:52s} {0:7d}")
            continue
        df = pd.DataFrame(lst, columns=["s", "t"])
        df["day"] = (df.t // 86400).astype(np.int64)
        df = df.drop_duplicates(["s", "day"])              # одна монета — одно событие в сутки
        m = pd.to_datetime(df.day * 86400, unit="s").dt.to_period("M")
        cnt = m.value_counts()
        v = np.array([int(cnt.get(mm, 0)) for mm in months])
        per_day = df.groupby("day").s.nunique()
        wide = df.day.map(per_day) >= 10
        days_m = pd.to_datetime(per_day.index.values * 86400, unit="s").to_period("M").value_counts()
        dv = np.array([int(days_m.get(mm, 0)) for mm in months])
        print(f"  {sig:52s} {len(df):7d} {v.mean():10.1f} {np.median(v):8.0f} {dv.mean():9.1f} {wide.mean():18.0%} {df.s.nunique():6d}")
        out.append(dict(period=name, signal=sig, n=len(df), per_month=v.mean(), median=np.median(v),
                        days_per_month=dv.mean(), wide_share=wide.mean(), coins=df.s.nunique()))


def main():
    out = []
    for name, path, a, b in PERIODS:
        t0, t1 = ts(a), ts(b)
        with open(os.path.join(D, path), "rb") as f:
            K = pickle.load(f)
        syms = [s for s in K if s not in BAD and not s.endswith("USDC") and "qv" in K[s]]
        rows_d, rows_4, rows_r = defaultdict(list), defaultdict(list), defaultdict(list)
        univ_days = 0
        for s in syms:
            x = agg(K[s], 86400)
            if x is None or len(x["T"]) < 60:
                continue
            S = daily_signals(x)
            ok = (x["qv"] >= VMIN) & (x["T"] >= t0) & (x["T"] < t1)
            univ_days += int(ok.sum())
            for sig, m in S.items():
                for tt in x["T"][m & ok]:
                    rows_d[sig].append((s, int(tt)))
            x4 = agg(K[s], 14400)
            if x4 is not None and len(x4["T"]) > 200:
                S4 = h4_signals(x4)
                v24 = pd.Series(x4["qv"]).rolling(6, min_periods=6).sum().values
                ok4 = (v24 >= VMIN) & (x4["T"] >= t0) & (x4["T"] < t1)
                for sig, m in S4.items():
                    for tt in x4["T"][m & ok4]:
                        rows_4[sig].append((s, int(tt)))
            for sig, tlist in round_events(K[s], s).items():
                for tt in tlist:
                    if t0 <= tt < t1:
                        rows_r[sig].append((s, int(tt)))
        print(f"\n##### {name}: перпов {len(syms)}, монето-дней во вселенной (оборот ≥ 5 млн $) {univ_days}, "
              f"в среднем монет в день {univ_days / ((t1 - t0) / 86400):.0f}")
        summarize(name + " — дневки", rows_d, t0, t1, out)
        summarize(name + " — 4 ч", rows_4, t0, t1, out)
        summarize(name + " — круглые числа (15 мин)", rows_r, t0, t1, out)
        ev = []
        for dct in (rows_d, rows_4, rows_r):
            for sig, lst in dct.items():
                ev += [(name, sig, s_, t_) for s_, t_ in lst]
        pd.DataFrame(ev, columns=["period", "signal", "s", "t"]).to_pickle(os.path.join(D, f"s179/crowd_events_{name}.pkl"))
        del K
    pd.DataFrame(out).to_pickle(os.path.join(D, "s179/crowd_freq.pkl"))


if __name__ == "__main__":
    main()
