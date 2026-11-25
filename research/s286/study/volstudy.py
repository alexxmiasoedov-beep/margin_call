"""s286 — описательные масштабы запланированных событий: |ход| BTC, ETH и альтов, всплеск оборота и ликвидаций,
сжатие перед событием — против тех же часов в дни без события. ТОЛЬКО абсолютные величины и счёт:
направленные доходы («куда пошла цена», продолжение, откат) и доходы сделок здесь НЕ считаются.

Периоды и свечи (15 мин, t — открытие свечи):
  2020–2022 — s117/k_2020.pkl; 2022–2024 — s117/k_oos.pkl; 2024–2026 — s2/k2y.pkl (заглушки с qv = 0 не берутся).
Цена в момент T — закрытие свечи, открытой в T − 15 мин; r_h = C(T + h) / C(T) − 1; до события — C(T) / C(T − 60 мин).
Альты — криптоперпы без BTC и ETH (s259 common: без TradFi, индексов, стейблкоинов), 50 крупнейших по обороту
за прошлые 7 сут, возраст ≥ 30 сут. «Медиана альтов» — медиана |r| по 50 монетам; «индекс альтов» — |среднее r|.
z-величины — |r| / σ монеты за прошлые 7 сут (σ 15-мин доходов × √(h/15)). Оборот — кратность к среднему обороту
того же отрезка за прошлые 7 сут. Ликвидации — канал BinanceLiquidations (s72, ≥ ~50 тыс. $, с 20.09.2024).
Контроль — те же местные часы и минуты события в дни без него (правила — CONTROL ниже), без «занятых» событий ±3 ч.

Запуск — из /home/user/mc_data: python3 -I <repo>/research/s286/study/volstudy.py
Итог — /home/user/mc_data/s286/vol_summary.csv, vol_profile.csv, vol_report.txt; поэлементные — /dev/shm/s286."""
import datetime as dt
import json
import os
import pickle
import re
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "s259", "study"))
from common259 import crypto_perps  # noqa: E402

BAR, DAY = 900, 86400
OUT, TMP = "/home/user/mc_data/s286", "/dev/shm/s286"
PER = {"2020–2022": ("s117/k_2020.pkl", "2020-10-01", "2022-10-01"),
       "2022–2024": ("s117/k_oos.pkl", "2022-10-01", "2024-10-01"),
       "2024–2026": ("s2/k2y.pkl", "2024-10-01", "2026-10-19")}
NALT, HZ = 50, (15, 30, 60, 120)
PROF = range(-4, 12)                      # профиль: 15-мин свечи от T − 60 до T + 180 мин
BUSY = {"CPI", "NFP", "PPI", "PCE", "RETAIL", "GDP", "GDP23", "JOLTS", "CLAIMS", "DURABLE", "HOUSING", "NHS", "TRADE",
        "ISM_M", "ISM_S", "FOMC", "FOMC_PC", "FOMC_MIN", "ECB", "ECB_PC", "BOJ", "BOJ_APPROX", "CN_PMI", "MSTR_BUY",
        "EARN_MSTR", "EARN_COIN", "EARN_HOOD", "EARN_MINER"}
NYSE_HOL = None


def ts(s):
    return int(pd.Timestamp(s, tz="UTC").timestamp())


# ---------- данные периода ----------
def load_period(p):
    kf, a, b = PER[p]
    K = pickle.load(open(kf, "rb"))
    t0, t1 = ts(a) - 9 * DAY, ts(b) + 2 * DAY           # запас на 7 сут истории и окна после
    n = (t1 - t0) // BAR
    coins = [c for c in crypto_perps(K) if c in K]
    for c in ("BTC", "ETH"):
        if c in K and c not in coins:
            coins.append(c)
    C = np.full((len(coins), n), np.nan, np.float32)
    Q = np.zeros((len(coins), n), np.float32)
    for j, c in enumerate(coins):
        x = K[c]
        tt = np.asarray(x["t"], np.int64)
        ok = (tt >= t0) & (tt < t1) & (np.asarray(x["qv"]) > 0)
        ii = (tt[ok] - t0) // BAR
        C[j, ii] = np.asarray(x["c"])[ok]
        Q[j, ii] = np.asarray(x["qv"])[ok]
    del K
    # пропуски цены — последним закрытием (не дальше 4 ч), чтобы окна редких сделок не выпадали
    df = pd.DataFrame(C.T)
    C = df.ffill(limit=16).to_numpy(np.float32).T
    return dict(coins=coins, C=C, Q=Q, t0=t0, n=n, a=ts(a), b=ts(b))


def daily_aux(D):
    """По суткам: оборот, σ 15-мин доходов и β к BTC за прошлые 7 сут, возраст; список 50 альтов на сутки."""
    C, Q, coins = D["C"], D["Q"], D["coins"]
    nd = D["n"] // 96
    r = np.diff(np.log(C), axis=1, prepend=np.nan)
    r[~np.isfinite(r)] = np.nan
    ib = coins.index("BTC")
    rb = r[ib]
    qd = Q[:, :nd * 96].reshape(len(coins), nd, 96).sum(2)
    rr = r[:, :nd * 96].reshape(len(coins), nd, 96)
    s2 = np.nansum(rr ** 2, 2)
    nn = np.isfinite(rr).sum(2)
    rbd = rb[:nd * 96].reshape(nd, 96)
    cxy = np.nansum(rr * rbd[None], 2)
    cyy = np.nansum(rbd ** 2, 1)

    def trail(x):
        cs = np.cumsum(np.concatenate([np.zeros((x.shape[0], 1)), x], 1), 1)
        out = np.full(x.shape, np.nan)
        out[:, 7:] = cs[:, 7:-1] - cs[:, :-8]
        return out
    q7 = trail(qd)
    sig = np.sqrt(trail(s2) / np.maximum(trail(nn.astype(float)), 1))
    cyy7 = trail(cyy[None])[0]
    beta = trail(cxy) / cyy7[None]
    first = np.array([np.argmax(qd[j] > 0) if (qd[j] > 0).any() else nd for j in range(len(coins))])
    age = np.arange(nd)[None] - first[:, None]
    alt = np.array([c not in ("BTC", "ETH") for c in coins])
    top = np.full((nd, NALT), -1, np.int64)
    for d in range(nd):
        v = np.where(alt & (age[:, d] >= 30) & np.isfinite(q7[:, d]) & (q7[:, d] > 0), q7[:, d], -1)
        o = np.argsort(-v)[:NALT]
        o = o[v[o] > 0]
        top[d, :len(o)] = o
    D.update(q7=q7, sig=sig, beta=beta, top=top, nd=nd, ib=ib, ie=coins.index("ETH") if "ETH" in coins else None)


def liq_series(D):
    """Ликвидации по 15-мин корзинам на сетке периода (с 20.09.2024): все монеты, BTC+ETH, прочие."""
    tot = np.zeros(D["n"]); maj = np.zeros(D["n"]); cnt = np.zeros(D["n"])
    rx = re.compile(r"#(\S+) Liquidated (Long|Short): \$([\d.]+)([KMB]?)")
    mult = {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}
    for ln in open("s72/liq.jsonl"):
        _, iso, txt = json.loads(ln)
        m = rx.search(txt)
        if not m:
            continue
        t = int(pd.Timestamp(iso).timestamp())
        i = (t - D["t0"]) // BAR
        if 0 <= i < D["n"]:
            v = float(m.group(3)) * mult[m.group(4)]
            tot[i] += v; cnt[i] += 1
            if m.group(1) in ("BTC", "ETH"):
                maj[i] += v
    D.update(liq=tot, liq_maj=maj, liq_n=cnt, liq_on=ts("2024-09-21"))


# ---------- метрики в моменты T ----------
def metrics(D, T):
    """T — массив моментов UTC (с); возвращает DataFrame по моментам (только абсолютные величины, β и R² — отдельно)."""
    C, Q = D["C"], D["Q"]
    T = np.asarray(T, np.int64)
    i = (T - D["t0"]) // BAR
    ok = (i >= 8 + 7 * 96) & (i + 12 < D["n"]) & (T >= D["a"]) & (T < D["b"])
    i, T = i[ok], T[ok]
    d = i // 96
    ib, ie = D["ib"], D["ie"]
    out = {"T": T}
    p0 = C[:, i - 1]                                          # монеты × моменты
    for h in HZ:
        rh = C[:, i - 1 + h // 15] / p0 - 1
        out[f"btc_a{h}"] = np.abs(rh[ib]) * 100
        if ie is not None:
            out[f"eth_a{h}"] = np.abs(rh[ie]) * 100
        sg = D["sig"][:, d] * np.sqrt(h / 15)
        z = np.abs(rh) / sg
        top = D["top"][d]                                     # моменты × 50
        A = np.take_along_axis(rh.T, np.maximum(top, 0), 1)
        Z = np.take_along_axis(z.T, np.maximum(top, 0), 1)
        A[top < 0] = np.nan; Z[top < 0] = np.nan
        out[f"alt_med_a{h}"] = np.nanmedian(np.abs(A), 1) * 100
        out[f"alt_med_z{h}"] = np.nanmedian(Z, 1)
        out[f"btc_z{h}"] = z[ib]
        out[f"alt_idx_r{h}"] = np.nanmean(A, 1) * 100          # знаковая — только для β/R², не для среднего
        out[f"btc_r{h}"] = rh[ib] * 100
        if h == 60:
            B = np.take_along_axis(D["beta"][:, d].T, np.maximum(top, 0), 1)
            B[top < 0] = np.nan
            e = A - B * rh[ib][:, None]
            out["alt_disp60"] = np.nanstd(e, 1) * 100          # разброс остатков альтов после β·BTC
    pre = p0 / C[:, i - 5] - 1
    out["btc_pre60"] = np.abs(pre[ib]) * 100
    top = D["top"][d]
    P = np.take_along_axis(pre.T, np.maximum(top, 0), 1); P[top < 0] = np.nan
    out["alt_med_pre60"] = np.nanmedian(np.abs(P), 1) * 100
    # оборот: кратность к среднему часу за прошлые 7 сут
    base = D["q7"][:, d] / (7 * 24)
    q_post = Q[:, i] + Q[:, i + 1] + Q[:, i + 2] + Q[:, i + 3]
    q_pre = Q[:, i - 4] + Q[:, i - 3] + Q[:, i - 2] + Q[:, i - 1]
    for nm, q in (("q60", q_post), ("qpre60", q_pre)):
        x = q / base
        out[f"btc_{nm}"] = x[ib]
        X = np.take_along_axis(x.T, np.maximum(top, 0), 1); X[top < 0] = np.nan
        out[f"alt_med_{nm}"] = np.nanmedian(X, 1)
    if "liq" in D:
        on = T >= D["liq_on"] + 7 * DAY
        cs = np.concatenate([[0], np.cumsum(D["liq"])])
        csm = np.concatenate([[0], np.cumsum(D["liq_maj"])])
        lb = (cs[i] - cs[i - 7 * 96]) / (7 * 24)                # средний час за 7 сут
        out["liq60_musd"] = np.where(on, (cs[i + 4] - cs[i]) / 1e6, np.nan)
        out["liqpre60_musd"] = np.where(on, (cs[i] - cs[i - 4]) / 1e6, np.nan)
        out["liq60_x"] = np.where(on & (lb > 0), (cs[i + 4] - cs[i]) / lb, np.nan)
        out["liq60_alt_share"] = np.where(on & (cs[i + 4] - cs[i] > 0),
                                          1 - (csm[i + 4] - csm[i]) / np.maximum(cs[i + 4] - cs[i], 1), np.nan)
    # профиль по 15-мин свечам
    for k in PROF:
        rk = np.abs(C[:, i + k] / C[:, i + k - 1] - 1)
        out[f"pb{k}"] = rk[ib] * 100
        R = np.take_along_axis(rk.T, np.maximum(top, 0), 1); R[top < 0] = np.nan
        out[f"pa{k}"] = np.nanmedian(R, 1) * 100
    return pd.DataFrame(out)


# ---------- контроль ----------
def local_hm(t, tz):
    x = pd.Timestamp(int(t), unit="s", tz="UTC")
    return x.tz_convert(tz) if tz != "UTC" else x


def control_times(E, fam, ev, busy_t, kind):
    """Те же местные часы:минуты события в дни-контроли. kind задаёт, какие дни годятся."""
    tz = ev.tz.iloc[0]
    hm = ev.t.map(lambda t: local_hm(t, tz).strftime("%H:%M")).mode().iloc[0]
    hh, mm = map(int, hm.split(":"))
    z = ZoneInfo(tz) if tz != "UTC" else dt.UTC
    evd = {local_hm(t, tz).date() for t in ev.t}
    out = []
    d = dt.date(2020, 9, 1)
    while d < dt.date(2026, 10, 25):
        t = int(dt.datetime(d.year, d.month, d.day, hh, mm, tzinfo=z).timestamp())
        good = kind(d) and d not in evd
        if good:
            j = np.searchsorted(busy_t, t - 3 * 3600)
            if j < len(busy_t) and busy_t[j] <= t + 3 * 3600:
                good = False
        if good:
            out.append(t)
        d += dt.timedelta(days=1)
    return np.array(out, np.int64), hm


def kinds(E):
    global NYSE_HOL
    import importlib.util
    spec = importlib.util.spec_from_file_location("be", os.path.join(HERE, "build_events.py"))
    be = importlib.util.module_from_spec(spec); spec.loader.exec_module(be)
    NYSE_HOL = be.NYSE_HOL
    globals()["NYSE_EARLY"] = be.NYSE_EARLY
    nyse = be.nyse_day
    W_DAYS = {pd.Timestamp(t, unit="s", tz="UTC").date() for t in E[E.fam == "DRB_W"].t}
    bday = lambda d: d.weekday() < 5                               # noqa: E731
    return {
        "nyse": nyse,
        "nyse_hol": lambda d: d.weekday() < 5 and not nyse(d),      # будни-праздники NYSE
        "weekend": lambda d: d.weekday() >= 5,
        "fri": lambda d: d.weekday() == 4 and nyse(d),
        "fri_any": lambda d: d.weekday() == 4,
        "mon_thu": lambda d: d.weekday() < 4 and nyse(d),
        "mon": lambda d: d.weekday() == 0 and nyse(d),
        "thu": lambda d: d.weekday() == 3,
        "sat": lambda d: d.weekday() == 5,
        "bday": bday,
        "all": lambda d: True,
        "fri_w": lambda d: d in W_DAYS,                                # обычные пятничные (недельные) экспирации Deribit
        "mon_thu_all": lambda d: d.weekday() < 4,
        "fri_not3": lambda d: d.weekday() == 4 and nyse(d) and not (15 <= d.day <= 21),
    }


# семья → (тип контрольных дней, описание); основной контроль — первый
CONTROL = {
    "CPI": ["nyse"], "NFP": ["nyse"], "PPI": ["nyse"], "PCE": ["nyse"], "RETAIL": ["nyse"], "GDP": ["nyse"],
    "GDP23": ["nyse"], "JOLTS": ["nyse"], "CLAIMS": ["nyse"], "DURABLE": ["nyse"], "HOUSING": ["nyse"], "NHS": ["nyse"],
    "TRADE": ["nyse"], "ISM_M": ["nyse"], "ISM_S": ["nyse"], "FOMC": ["nyse"], "FOMC_PC": ["nyse"],
    "FOMC_MIN": ["nyse"], "ECB": ["bday"], "ECB_PC": ["bday"], "BOJ": ["bday"], "BOJ_APPROX": ["bday"],
    "CN_PMI": ["all"], "US_OPEN": ["nyse_hol", "weekend"], "US_10": ["nyse_hol", "weekend"],
    "US_CLOSE": ["nyse_hol", "weekend"], "ETF_FIX": ["nyse_hol", "weekend"], "OPEX_M": ["fri_not3"],
    "OPEX_Q": ["fri_not3"], "OPEX_SOQ": ["fri_not3"], "IBIT_W": ["mon_thu"], "DRB_M": ["fri_w"], "DRB_Q": ["fri_w"], "DRB_W": ["mon_thu_all"],
    "BN_DELIV": ["fri_w"], "CME_EXP": ["fri"], "CME_CLOSE": ["thu", "sat"], "CME_OPEN": ["sat"],
    "EARN_MSTR": ["nyse"], "EARN_COIN": ["nyse"], "EARN_HOOD": ["nyse"], "EARN_MINER": ["nyse"], "MSTR_BUY": ["mon"],
    "NY1500": ["nyse_hol", "weekend"], "FRI_1600": ["mon_thu"], "CME_OPEN_247": ["sat"],
}
COLS = ["btc_a15", "btc_a60", "eth_a60", "alt_med_a15", "alt_med_a60", "alt_med_z60", "btc_z60", "alt_disp60",
        "btc_pre60", "alt_med_pre60", "btc_q60", "alt_med_q60", "btc_qpre60", "alt_med_qpre60", "liq60_musd",
        "liq60_x", "liq60_alt_share"]


def summarize(m_e, m_c, fam, per, ctl, hm, n_mo):
    r = {"fam": fam, "period": per, "control": ctl, "local": hm, "n": len(m_e), "n_ctl": len(m_c),
         "per_month": round(len(m_e) / n_mo, 2)}
    for c in COLS:
        if c not in m_e or m_e[c].notna().sum() < 3 or m_c[c].notna().sum() < 3:
            continue
        a, b = m_e[c].dropna(), m_c[c].dropna()
        r[c + "_ev"] = round(a.median(), 4)
        r[c + "_ctl"] = round(b.median(), 4)
        r[c + "_x"] = round(a.median() / b.median(), 2) if b.median() > 0 else np.nan
    if len(m_e) >= 5 and len(m_c) >= 5:
        u = stats.mannwhitneyu(m_e.alt_med_z60.dropna(), m_c.alt_med_z60.dropna())
        r["mw_p_alt_z60"] = float(u.pvalue)
        # «макро-β»: наклон знакового хода индекса альтов на знаковый ход BTC за 60 мин (ко-движение, не прогноз)
        for nm, m in (("ev", m_e), ("ctl", m_c)):
            x, y = m.btc_r60.to_numpy(), m.alt_idx_r60.to_numpy()
            k = np.isfinite(x) & np.isfinite(y)
            if k.sum() >= 5 and np.var(x[k]) > 0:
                bb = np.cov(x[k], y[k])[0, 1] / np.var(x[k], ddof=1)
                r[f"beta60_{nm}"] = round(bb, 2)
                r[f"r2_60_{nm}"] = round(np.corrcoef(x[k], y[k])[0, 1] ** 2, 2)
        # доля событий, где |ход| альтов выше 90-го перцентиля контроля
        q90 = np.nanpercentile(m_c.alt_med_z60, 90)
        r["share_gt_ctl90"] = round(float((m_e.alt_med_z60 > q90).mean()), 2)
    return r


def main():
    E = pd.read_csv(f"{OUT}/events.csv")
    busy_t = np.sort(E[E.fam.isin(BUSY)].t.to_numpy())
    K = kinds(E)
    rows, prof = [], []
    for per in PER:
        D = load_period(per)
        daily_aux(D)
        if per == "2024–2026":
            liq_series(D)
        a, b = D["a"], D["b"]
        n_mo = (b - a) / (30.44 * DAY)
        allm = []
        for fam, ev in E.groupby("fam"):
            if fam not in CONTROL:
                continue
            ev = ev[(ev.t >= a) & (ev.t < b)]
            if len(ev) < 3:
                continue
            m_all = metrics(D, ev.t.to_numpy())
            m_all["fam"] = fam
            allm.append(m_all)
            # для своей семьи «занятые» — все прочие события, кроме её собственных моментов
            bt = np.sort(E[E.fam.isin(BUSY) & (E.fam != fam)].t.to_numpy())
            # «чистые» события — без других занятых событий в ±3 ч (у часов NYSE, экспираций и т. п.)
            tt = m_all["T"].to_numpy()
            j = np.searchsorted(bt, tt - 3 * 3600)
            clean = ~((j < len(bt)) & (bt[np.minimum(j, len(bt) - 1)] <= tt + 3 * 3600))
            sets = [("all", m_all)] + ([("clean", m_all[clean])] if 0 < (~clean).sum() and clean.sum() >= 5 else [])
            for ctl in CONTROL[fam]:
                ct, hm = control_times(E, fam, ev, bt if fam in BUSY else busy_t, K[ctl])
                m_c = metrics(D, ct)
                if len(m_c) < 5:
                    continue
                for evset, m_e in sets:
                    r = summarize(m_e, m_c, fam, per, ctl, hm, n_mo)
                    r["events"] = evset
                    rows.append(r)
                    for k in PROF:
                        prof.append(dict(fam=fam, period=per, control=ctl, events=evset, k=k,
                                         btc_ev=m_e[f"pb{k}"].median(), btc_ctl=m_c[f"pb{k}"].median(),
                                         alt_ev=m_e[f"pa{k}"].median(), alt_ctl=m_c[f"pa{k}"].median()))
        pd.concat(allm).to_pickle(f"{TMP}/ev_metrics_{per}.pkl")
        print(per, "готово", flush=True)
        del D
    s = pd.DataFrame(rows)
    s.to_csv(f"{OUT}/vol_summary.csv", index=False)
    pd.DataFrame(prof).to_csv(f"{OUT}/vol_profile.csv", index=False)
    show = ["fam", "period", "control", "events", "local", "n", "per_month", "btc_a60_ev", "btc_a60_x", "alt_med_a60_ev",
            "alt_med_a60_x", "alt_med_z60_x", "btc_pre60_x", "alt_med_pre60_x", "btc_q60_x", "alt_med_q60_x",
            "alt_disp60_x", "liq60_x_x", "beta60_ev", "beta60_ctl", "share_gt_ctl90", "mw_p_alt_z60"]
    with open(f"{OUT}/vol_report.txt", "w") as f:
        f.write(s[[c for c in show if c in s]].to_string(index=False))
    print(s[[c for c in show if c in s]].to_string(index=False))


if __name__ == "__main__":
    main()
