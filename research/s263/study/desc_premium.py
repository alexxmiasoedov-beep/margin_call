"""s263 — премия перпа к индексу (premiumIndexKlines 15m из архива Binance, bv_fetch.py) по сессиям базового рынка,
часам недели и до/после перевода индекса вне часов торгов в режим Orderbook EWMA (сырьё 08.05.2026 21:00 UTC,
акции 16.05.2026 00:00 UTC). Премия P = [max(0, impact bid − индекс) − max(0, индекс − impact ask)] / индекс,
считается раз в 5 с; свеча 15 мин даёт open/high/low/close этих значений. Доходов сделок не считает.

Запуск из /home/user/mc_data: python3 -I <путь>/desc_premium.py"""
import datetime
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common263 import (SHM, UTC, cme_session, cn_session, group, hk_session, kr_session, load_meta,  # noqa: E402
                       us_session)

T0 = int(datetime.datetime(2025, 12, 1, tzinfo=UTC).timestamp())
T1 = int(datetime.datetime(2026, 11, 20, tzinfo=UTC).timestamp())
SW_EQ = int(datetime.datetime(2026, 5, 16, tzinfo=UTC).timestamp())
SW_CM = int(datetime.datetime(2026, 5, 8, 21, tzinfo=UTC).timestamp())
FN = {"US_STOCK": us_session, "US_ETF": us_session, "US_LEV": us_session, "PREMARKET": us_session,
      "COMMODITY": cme_session, "FX": cme_session, "KR_EQUITY": kr_session, "HK_EQUITY": hk_session,
      "CN_EQUITY": cn_session}


def grids():
    g = np.arange(T0, T1, 900)
    return {k: f(g) for k, f in {"us": us_session, "cme": cme_session, "kr": kr_session, "hk": hk_session,
                                  "cn": cn_session}.items()}


def main():
    P = pickle.load(open(f"{SHM}/bv_premiumIndexKlines_15m.pkl", "rb"))
    meta = load_meta()
    meta = meta[meta.k_n > 0].copy()
    meta["grp"] = [group(s, u) for s, u in zip(meta.sym, meta.ut)]
    G = grids()
    key = {"US_STOCK": "us", "US_ETF": "us", "US_LEV": "us", "PREMARKET": "us", "COMMODITY": "cme", "FX": "cme",
           "KR_EQUITY": "kr", "HK_EQUITY": "hk", "CN_EQUITY": "cn"}
    rows = []
    for r in meta.itertuples():
        a = P.get(r.sym)
        if a is None or not len(a):
            continue
        t = a[:, 0].astype(np.int64)
        m = (t >= T0) & (t < T1)
        t, cl, hi, lo, cnt = t[m], a[m, 4], a[m, 2], a[m, 3], a[m, 5]
        ses = G[key[r.grp]][(t - T0) // 900]
        sw = SW_CM if r.grp in ("COMMODITY", "FX") else SW_EQ
        rows.append(pd.DataFrame(dict(sym=r.sym, grp=r.grp, t=t, p=cl, hi=hi, lo=lo, cnt=cnt, ses=ses, post=t >= sw)))
    D = pd.concat(rows, ignore_index=True)
    D = D[D.cnt > 0]
    D["wd"] = (D.t // 86400 + 3) % 7
    D["hr"] = (D.t // 3600) % 24
    D.to_pickle(f"{SHM}/premium_rows.pkl")
    bp = lambda x: x * 1e4  # noqa: E731
    print(f"свечей премии: {len(D):,}; символов {D.sym.nunique()}")
    print("\nПремия по сессиям (б. п.; после перевода индекса в Orderbook EWMA вне часов торгов): медиана, среднее,"
          " медиана |P|, доля |P| > 5 б. п. (порог, с которого начисляется фандинг при процентной ставке 0)")
    for g, x in D[D.post].groupby("grp"):
        for s, y in x.groupby("ses"):
            print(f"  {g:9s} {s:6s} n={len(y):7d} мед {bp(y.p.median()):+6.2f} ср {bp(y.p.mean()):+6.2f} "
                  f"|P| мед {bp(y.p.abs().median()):5.2f} |P|>5 {(y.p.abs() > 5e-4).mean():5.1%} "
                  f"|P|>20 {(y.p.abs() > 2e-3).mean():5.1%}")
    print("\nВыходные до и после перевода индекса (фиксированный индекс → Orderbook EWMA): медиана P, медиана |P|, p95 |P| (б. п.)")
    for g, x in D.groupby("grp"):
        for post, y in x[x.ses == "WKND"].groupby("post"):
            print(f"  {g:9s} {'после' if post else 'до   '} n={len(y):6d} мед {bp(y.p.median()):+7.2f} |P| мед "
                  f"{bp(y.p.abs().median()):7.2f} p95 {bp(y.p.abs().quantile(.95)):8.2f}")
    print("\nАкции США (одиночные), после перевода: медиана P по часу UTC (б. п.), будни / выходные:")
    x = D[(D.grp == "US_STOCK") & D.post]
    wk = x[x.wd < 5].groupby("hr").p.median()
    we = x[x.wd >= 5].groupby("hr").p.median()
    print("  будни   " + " ".join(f"{bp(v):+5.1f}" for v in wk.values))
    print("  вых.    " + " ".join(f"{bp(v):+5.1f}" for v in we.values))
    for g in ("US_LEV", "US_ETF", "COMMODITY", "KR_EQUITY", "HK_EQUITY"):
        x = D[(D.grp == g) & D.post & (D.wd < 5)].groupby("hr").p.median()
        print(f"  {g:9s}будни " + " ".join(f"{bp(v):+5.1f}" for v in x.values))
    # по символам: средняя премия за последние 60 сут в разные сессии (топ по обороту)
    vol = pd.read_csv("s263/desc_volume_sym.csv").set_index("sym").qv30
    top = list(vol.sort_values(ascending=False).index[:25])
    T60 = T1 - 60 * 86400
    print("\nТоп-25 по обороту: средняя P за последние 60 сут по сессиям (б. п.)")
    y = D[(D.t >= T60) & D.sym.isin(top)].groupby(["sym", "ses"]).p.mean().unstack()
    y = (y * 1e4).round(1).reindex(top)
    print(y.to_string())
    # доля времени, когда премия упирается в «полосу» отклонения марк-цены (±3/±5%), — грубо по high/low
    print("\nСвечи с |P| ≥ 1% (по high/low) — доля по группам и сессиям, после перевода:")
    x = D[D.post].assign(ext=lambda d: np.maximum(d.hi.abs(), d.lo.abs()) >= 0.01)
    print((x.groupby(["grp", "ses"]).ext.mean() * 100).round(2).unstack().to_string())


if __name__ == "__main__":
    main()
