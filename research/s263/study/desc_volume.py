"""s263 — описание оборота TradFi-перпов по 15-мин свечам (s224/k_d.pkl через extract.py): кто крупный, когда торгуют
(часы суток UTC, дни недели, сессии базового рынка), сравнение с BTC. Доходов не считает.

Запуск из /home/user/mc_data: python3 -I <путь>/desc_volume.py"""
import datetime
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common263 import (UTC, cme_session, cn_session, fmt_ts, group, hk_session, kr_session, load_k, load_meta,  # noqa
                       us_session)

T_END = int(datetime.datetime(2026, 11, 20, tzinfo=UTC).timestamp())
T30 = T_END - 30 * 86400


def main():
    K = load_k()
    meta = load_meta()
    meta = meta[meta.k_n > 0].copy()
    meta["grp"] = [group(s, u) for s, u in zip(meta.sym, meta.ut)]
    rows = []
    for r in meta.itertuples():
        a = K[r.sym]
        t, qv = a["t"], a["qv"].astype(float)
        live = qv > 0
        first = int(t[live][0])
        last30 = (t >= T30) & (t < T_END)
        days30 = max(1.0, min(30.0, (T_END - max(first, T30)) / 86400))
        rows.append(dict(sym=r.sym, grp=r.grp, first=first, qv_all=qv.sum(), qv30=qv[last30].sum() / days30,
                         zero30=float((qv[last30] == 0).mean()) if last30.any() else np.nan))
    D = pd.DataFrame(rows).sort_values("qv30", ascending=False)
    D.to_csv("s263/desc_volume_sym.csv", index=False)
    tot = D.qv30.sum()
    btc = K["BTC"]; m = (btc["t"] >= T30) & (btc["t"] < T_END)
    print(f"Оборот TradFi за последние 30 сут (20.10–19.11.2026): {tot / 1e9:.2f} млрд $ в сутки; BTC-перп "
          f"{btc['qv'][m].sum() / 30 / 1e9:.2f} млрд $ в сутки; ETH {K['ETH']['qv'][(K['ETH']['t'] >= T30) & (K['ETH']['t'] < T_END)].sum() / 30 / 1e9:.2f}")
    g = D.groupby("grp").agg(n=("sym", "size"), qv30=("qv30", "sum")).sort_values("qv30", ascending=False)
    g["share"] = g.qv30 / tot
    print(g.to_string(formatters={"qv30": lambda x: f"{x / 1e6:,.0f} млн", "share": lambda x: f"{x:.1%}"}))
    print("\nТоп-30 по обороту в сутки (млн $), дата запуска:")
    for r in D.head(30).itertuples():
        print(f"  {r.sym:14s} {r.grp:9s} {r.qv30 / 1e6:8.0f}  с {fmt_ts(r.first)[:10]}  пустых свечей {r.zero30:.0%}")
    q = D.qv30.values
    print(f"\nКонцентрация: топ-5 {q[:5].sum() / tot:.0%}, топ-10 {q[:10].sum() / tot:.0%}, топ-30 {q[:30].sum() / tot:.0%};"
          f" с оборотом ≥ 10 млн $ в сутки — {int((q >= 1e7).sum())}, ≥ 50 млн — {int((q >= 5e7).sum())}, "
          f"≥ 100 млн — {int((q >= 1e8).sum())}")
    # по месяцам: общий оборот TradFi и доля от BTC
    print("\nПо месяцам: оборот TradFi в сутки (млн $), число живых контрактов, к BTC-перпу:")
    allt = []
    for s in list(D.sym):
        a = K[s]; allt.append(pd.Series(a["qv"].astype(float), index=pd.to_datetime(a["t"], unit="s", utc=True)))
    S = pd.concat(allt, axis=1).fillna(0)
    S.columns = list(D.sym)
    mon = S.resample("MS").sum()
    nd = S.resample("MS").size() / 96
    b = pd.Series(btc["qv"].astype(float), index=pd.to_datetime(btc["t"], unit="s", utc=True)).resample("MS").sum()
    for d, row in mon.iterrows():
        if d < pd.Timestamp("2025-12-01", tz="UTC"):
            continue
        live = int((row > 0).sum())
        print(f"  {d:%Y-%m}: {row.sum() / nd[d] / 1e6:8.0f}  контрактов {live:3d}  к BTC {row.sum() / b.get(d, np.nan):.1%}")
    # профиль по часам UTC и дням недели: последние 60 сут, по группам
    T60 = T_END - 60 * 86400
    print("\nДоля оборота по часам UTC (последние 60 сут; группа → 24 числа, % суточного оборота):")
    prof = {}
    for gname, syms in list(D.groupby("grp").sym) + [("BTC", pd.Series(["BTC"]))]:
        acc = np.zeros(24)
        wk = np.zeros(7)
        for s in syms:
            a = K[s]; m = (a["t"] >= T60) & (a["t"] < T_END)
            h = ((a["t"][m] // 3600) % 24).astype(int)
            np.add.at(acc, h, a["qv"][m].astype(float))
            wd = ((a["t"][m] // 86400 + 3) % 7).astype(int)  # 0 = пн
            np.add.at(wk, wd, a["qv"][m].astype(float))
        prof[gname] = (acc / acc.sum(), wk / wk.sum())
        print(f"  {gname:9s} " + " ".join(f"{x * 100:4.1f}" for x in acc / acc.sum()))
    print("\nДоля оборота по дням недели (пн…вс), последние 60 сут:")
    for gname, (_, wk) in prof.items():
        print(f"  {gname:9s} " + " ".join(f"{x * 100:5.1f}" for x in wk))
    # сессии: доля времени и доля оборота
    print("\nСессии базового рынка: доля времени и доля оборота (последние 60 сут):")
    for gname, syms in D.groupby("grp").sym:
        fn = {"US_STOCK": us_session, "US_ETF": us_session, "US_LEV": us_session, "COMMODITY": cme_session,
              "KR_EQUITY": kr_session, "HK_EQUITY": hk_session, "CN_EQUITY": cn_session, "FX": cme_session,
              "PREMARKET": us_session}[gname]
        tt = np.arange(T60, T_END, 900)
        ses = fn(tt)
        qv = np.zeros(len(tt))
        for s in syms:
            a = K[s]; m = (a["t"] >= T60) & (a["t"] < T_END)
            i = ((a["t"][m] - T60) // 900).astype(int)
            np.add.at(qv, i, a["qv"][m].astype(float))
        out = []
        for k in sorted(set(ses)):
            mm = ses == k
            out.append(f"{k} время {mm.mean():.0%} оборот {qv[mm].sum() / qv.sum():.0%} (×{qv[mm].sum() / qv.sum() / mm.mean():.2f})")
        print(f"  {gname:9s} " + "; ".join(out))
    btc_t = np.arange(T60, T_END, 900)
    ses = us_session(btc_t)
    a = K["BTC"]; m = (a["t"] >= T60) & (a["t"] < T_END)
    qv = np.zeros(len(btc_t)); np.add.at(qv, ((a["t"][m] - T60) // 900).astype(int), a["qv"][m].astype(float))
    print("  BTC (по часам акций США) " + "; ".join(f"{k} время {(ses == k).mean():.0%} оборот {qv[ses == k].sum() / qv.sum():.0%}"
                                              for k in sorted(set(ses))))


if __name__ == "__main__":
    main()
