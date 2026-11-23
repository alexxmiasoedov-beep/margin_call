"""s263 — «переякорение» индекса при открытии базового рынка: насколько индекс в первые 15 мин после открытия
расходится с ценой перпа перед открытием (|J|), и насколько перп ушёл, пока индекс был в режиме Orderbook EWMA (|M|).
Для будних открытий (KRX, HKEX, CME после перерыва, утро США 9:30) считается ещё и доля хода перпа вне часов,
которую подтвердил индекс при открытии (наклон b в J = a + (b − 1)·M; b = 1 — перп угадал всё, b = 0 — ход перпа шум);
для ВЫХОДНЫХ направление не считается: его проверяет s74 в 2027 г. (условие исследования — доходы выходных не трогать).

Запуск из /home/user/mc_data: python3 -I <путь>/desc_reopen.py
Нужны: /dev/shm/s263/tf_k.pkl, bv_indexPriceKlines_15m.pkl, bv_premiumIndexKlines_15m.pkl."""
import datetime
import os
import pickle
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common263 import NYSE_HOLI, SHM, UTC, group, load_k, load_meta  # noqa: E402

NY = ZoneInfo("America/New_York")
SEOUL = ZoneInfo("Asia/Seoul")
HKT = ZoneInfo("Asia/Hong_Kong")
D0 = datetime.date(2026, 5, 17)          # после перевода индекса акций в Orderbook EWMA (16.05.2026)
D1 = datetime.date(2026, 11, 19)
KRX_HOLI = {"2026-05-25", "2026-06-03", "2026-08-17", "2026-09-24", "2026-09-25", "2026-10-05", "2026-10-09"}
HK_HOLI = {"2026-05-25", "2026-06-19", "2026-07-01", "2026-09-26", "2026-10-01", "2026-10-19"}


def ts(d, hh, mm, tz):
    return int(datetime.datetime(d.year, d.month, d.day, hh, mm, tzinfo=tz).timestamp())


def at(arr, T):
    """Значение закрытия свечи, которая закрывается в T (открытие T − 900); None, если её нет."""
    t = arr[:, 0]
    i = int(np.searchsorted(t, T - 900))
    if i < len(t) and int(t[i]) == T - 900:
        return float(arr[i, 4])
    return None


def kat(K, s, T):
    a = K[s]; t = a["t"]
    i = int(np.searchsorted(t, T - 900))
    if i < len(t) and int(t[i]) == T - 900 and a["qv"][i] > 0:
        return float(a["c"][i])
    return None


def events():
    """(группа-ключ, вид, момент последней цены базового рынка C, момент открытия T)."""
    ev = []
    d = D0
    while d <= D1:
        wd = d.weekday()
        ds = d.isoformat()
        # США: открытие ночной сессии в воскресенье 20:00 ET после выходных; утро 9:30 ET в будни
        if wd == 6:
            fri = d - datetime.timedelta(2)
            mon = d + datetime.timedelta(1)
            if mon.isoformat() not in NYSE_HOLI:
                ev.append(("us", "WKND", ts(fri, 20, 0, NY), ts(d, 20, 0, NY)))
        if wd < 5 and ds not in NYSE_HOLI:
            # C = T: M — отрыв перпа от индекса (EWMA премаркета) прямо перед открытием
            ev.append(("us", "OPEN930", ts(d, 9, 30, NY), ts(d, 9, 30, NY)))
        # CME: воскресенье 18:00 ET после выходных; будни 18:00 ET после перерыва 17–18
        if wd == 6:
            fri = d - datetime.timedelta(2)
            ev.append(("cme", "WKND", ts(fri, 17, 0, NY), ts(d, 18, 0, NY)))
        if wd < 4:
            ev.append(("cme", "BREAK", ts(d, 17, 0, NY), ts(d, 18, 0, NY)))
        # KRX: 09:00 KST в будни; предыдущее закрытие 15:20 KST прошлого рабочего дня
        if wd < 5 and ds not in KRX_HOLI:
            prev = d - datetime.timedelta(1)
            while prev.weekday() >= 5 or prev.isoformat() in KRX_HOLI:
                prev -= datetime.timedelta(1)
            kind = "DAILY" if (d - prev).days == 1 else "WKND"
            ev.append(("kr", kind, ts(prev, 15, 15, SEOUL), ts(d, 9, 0, SEOUL)))
        # HKEX: 09:30 HKT
        if wd < 5 and ds not in HK_HOLI:
            prev = d - datetime.timedelta(1)
            while prev.weekday() >= 5 or prev.isoformat() in HK_HOLI:
                prev -= datetime.timedelta(1)
            kind = "DAILY" if (d - prev).days == 1 else "WKND"
            ev.append(("hk", kind, ts(prev, 16, 0, HKT), ts(d, 9, 30, HKT)))
        d += datetime.timedelta(1)
    return ev


def main():
    K = load_k()
    I = pickle.load(open(f"{SHM}/bv_indexPriceKlines_15m.pkl", "rb"))
    meta = load_meta()
    meta = meta[meta.k_n > 0].copy()
    meta["grp"] = [group(s, u) for s, u in zip(meta.sym, meta.ut)]
    gk = {"US_STOCK": "us", "US_ETF": "us", "US_LEV": "us", "COMMODITY": "cme", "KR_EQUITY": "kr", "HK_EQUITY": "hk"}
    EV = events()
    rows = []
    for r in meta.itertuples():
        k = gk.get(r.grp)
        if k is None or r.sym not in I:
            continue
        ia = I[r.sym]
        for key, kind, C, T in EV:
            if key != k or C < r.onboard + 3 * 86400:
                continue
            p_pre = kat(K, r.sym, T)          # перп в момент открытия (закрытие свечи до T)
            i_c = at(ia, C)                    # индекс на последней цене базового рынка
            i_post = at(ia, T + 900)           # индекс через 15 мин после открытия
            p_post = kat(K, r.sym, T + 900)
            if None in (p_pre, i_c, i_post, p_post):
                continue
            rows.append(dict(sym=r.sym, grp=r.grp, key=k, kind=kind, te=T, M=p_pre / i_c - 1, J=i_post / p_pre - 1,
                             R=p_post / p_pre - 1, qv=float(r.k_n)))
    D = pd.DataFrame(rows)
    D.to_pickle(f"{SHM}/reopen_rows.pkl")
    vol = pd.read_csv("s263/desc_volume_sym.csv").set_index("sym").qv30
    D["liq"] = D.sym.map(vol).fillna(0) >= 2e7
    print(f"событий открытия: {len(D):,} (символ × открытие), {D.sym.nunique()} символов, {datetime.datetime.fromtimestamp(D.te.min(), UTC):%Y-%m-%d} – "
          f"{datetime.datetime.fromtimestamp(D.te.max(), UTC):%Y-%m-%d}")
    pct = lambda x: f"{x * 100:.2f}%"  # noqa: E731
    print("\nВеличины (только ликвидные: оборот ≥ 20 млн $ в сутки за последние 30 сут): медиана и p90 |M| — ход перпа"
          " вне часов к последней цене базового рынка; |J| — разрыв индекса через 15 мин после открытия с ценой перпа"
          " перед открытием; доли |J| ≥ 1%, ≥ 3%, ≥ 5%; событий в месяц (символ × открытие)")
    months = (D.te.max() - D.te.min()) / (30.4 * 86400)
    for (g, kind), x in D[D.liq].groupby(["grp", "kind"]):
        print(f"  {g:9s} {kind:7s} n={len(x):5d} ({len(x) / months:6.1f}/мес) |M| мед {pct(x.M.abs().median())} p90 "
              f"{pct(x.M.abs().quantile(.9))} | |J| мед {pct(x.J.abs().median())} p90 {pct(x.J.abs().quantile(.9))} "
              f"≥1% {(x.J.abs() >= .01).mean():.0%} ≥3% {(x.J.abs() >= .03).mean():.1%} ≥5% {(x.J.abs() >= .05).mean():.1%}")
    print("\nДоля хода перпа вне часов, подтверждённая индексом при открытии (будни; b = 1 + наклон J по M; кластер — день):")
    for (g, kind), x in D[D.liq & (D.kind != "WKND")].groupby(["grp", "kind"]):
        if len(x) < 50:
            continue
        X = np.c_[np.ones(len(x)), x.M.values]
        beta, *_ = np.linalg.lstsq(X, x.J.values, rcond=None)
        e = x.J.values - X @ beta
        day = (x.te.values // 86400)
        # кластерная ошибка по дням
        XtX = np.linalg.inv(X.T @ X)
        meat = np.zeros((2, 2))
        for dd in np.unique(day):
            m = day == dd
            sg = X[m].T @ e[m]
            meat += np.outer(sg, sg)
        se = np.sqrt(np.diag(XtX @ meat @ XtX))
        print(f"  {g:9s} {kind:7s} n={len(x):5d} b = {1 + beta[1]:+.2f} (± {1.96 * se[1]:.2f}); корреляция M и J "
              f"{np.corrcoef(x.M, x.J)[0, 1]:+.2f}")


if __name__ == "__main__":
    main()
