"""s263 — связи между перпами (описание, без доходов сделок):
1) связь с BTC: корреляция и бета часовых изменений перпов акций США по сессиям (REG / PRE / POST / ON / WKND);
2) согласованность плечевых ETF с базовым перпом в выходные: e = r(плечевой) − L·r(базовый) за пт 20:00 → вс 19:45 ET
   (в выходные оба индекса — Orderbook EWMA, цену ставят только перповые трейдеры; при открытии всё сводится к NAV);
3) АДР SK hynix (SKHY, Nasdaq) и SKHYNIX (KRX): отношение цен и его колебания; часы, когда «живой» индекс только у одного;
4) корейские перпы в часы торгов США: корреляция часовых изменений SKHYNIX и SAMSUNG с полупроводниками США.

Запуск из /home/user/mc_data: python3 -I <путь>/desc_cross.py"""
import datetime
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common263 import NYSE_HOLI, UTC, group, kr_session, load_k, load_meta, us_session  # noqa: E402

NY = ZoneInfo("America/New_York")
T_END = int(datetime.datetime(2026, 11, 20, tzinfo=UTC).timestamp())
T0 = int(datetime.datetime(2026, 5, 17, tzinfo=UTC).timestamp())
PAIRS = [("SOXL", "SMH", 3), ("SOXS", "SMH", -3), ("SOXL", "SOXS", -1), ("TQQQ", "QQQ", 3), ("SQQQ", "QQQ", -3),
         ("TSLL", "TSLA", 2), ("NVDL", "NVDA", 2), ("MSTU", "MSTR", 2), ("MUU", "MU", 2), ("KORU", "EWY", 3),
         ("SKUU", "SKHY", 2), ("SKDD", "SKHY", -2), ("TZA", "IWM", -3)]


def hourly(K, s):
    a = K[s]
    t = a["t"]; c = a["c"].astype(float); qv = a["qv"]
    m = (t % 3600 == 2700) & (qv >= 0)            # закрытие часовой свечи — свеча 15 мин, открытая в :45
    return pd.Series(c[m], index=t[m] + 900)


def main():
    K = load_k()
    meta = load_meta()
    meta = meta[meta.k_n > 0].copy()
    meta["grp"] = [group(s, u) for s, u in zip(meta.sym, meta.ut)]
    vol = pd.read_csv("s263/desc_volume_sym.csv").set_index("sym").qv30
    liq = [s for s in meta.sym[meta.grp.isin(["US_STOCK", "US_ETF", "US_LEV"])] if vol.get(s, 0) >= 5e7]
    btc = hourly(K, "BTC")
    rb = np.log(btc).diff()
    print("1) Связь с BTC, часовые изменения, ликвидные акции и фонды США (оборот ≥ 50 млн $ в сутки), с 17.05.2026:")
    rows = []
    for s in liq:
        p = hourly(K, s)
        r = np.log(p).diff()
        j = r.index.intersection(rb.index)
        j = j[(j >= T0) & (j < T_END)]
        x, y = r.loc[j], rb.loc[j]
        ses = pd.Series(us_session(np.asarray(j, dtype=np.int64) - 3600), index=j)   # сессия часа (по его началу)
        for sname in ("REG", "PRE", "POST", "ON", "WKND"):
            m = (ses == sname).values & np.isfinite(x.values) & np.isfinite(y.values)
            if m.sum() < 100:
                continue
            c = np.corrcoef(x.values[m], y.values[m])[0, 1]
            b = np.cov(x.values[m], y.values[m])[0, 1] / np.var(y.values[m])
            rows.append(dict(sym=s, ses=sname, corr=c, beta=b, vol=np.std(x.values[m]) * 100, n=int(m.sum())))
    B = pd.DataFrame(rows)
    print(B.groupby("ses")[["corr", "beta", "vol"]].median().round(3).reindex(["REG", "PRE", "POST", "ON", "WKND"]).to_string())
    print("   (vol — σ часового изменения перпа, %; медианы по символам)")
    # 2) плечевые ETF в выходные
    print("\n2) Выходные: e = r(плечевой) − L·r(базовый), пт 20:00 → вс 19:45 ET (оба перпа), в п. п.:")
    rows = []
    d = datetime.date(2026, 5, 22)
    while d <= datetime.date(2026, 11, 13):
        if (d + datetime.timedelta(3)).isoformat() not in NYSE_HOLI and d.isoformat() not in NYSE_HOLI:
            C = int(datetime.datetime(d.year, d.month, d.day, 20, 0, tzinfo=NY).timestamp())
            sun = d + datetime.timedelta(2)
            E = int(datetime.datetime(sun.year, sun.month, sun.day, 19, 45, tzinfo=NY).timestamp())
            for a, b, L in PAIRS:
                if a not in K or b not in K:
                    continue
                pa, pb = [], []
                for s, out in ((a, pa), (b, pb)):
                    t = K[s]["t"]; c = K[s]["c"]
                    for T in (C, E):
                        i = int(np.searchsorted(t, T - 900))
                        out.append(float(c[i]) if i < len(t) and t[i] == T - 900 and K[s]["qv"][i] > 0 else np.nan)
                ra, rb2 = pa[1] / pa[0] - 1, pb[1] / pb[0] - 1
                if np.isfinite(ra) and np.isfinite(rb2):
                    rows.append(dict(pair=f"{a}/{b}", L=L, wk=d.isoformat(), ra=ra, rb=rb2, e=ra - L * rb2))
        d += datetime.timedelta(7)
    W = pd.DataFrame(rows)
    W.to_csv("s263/letf_weekend_consistency.csv", index=False)
    for p, x in W.groupby("pair"):
        print(f"  {p:11s} выходных {len(x):2d}: медиана |r база| {x.rb.abs().median() * 100:5.2f}%, медиана |e| "
              f"{x.e.abs().median() * 100:5.2f} п. п., p90 |e| {x.e.abs().quantile(.9) * 100:5.2f}, "
              f"корр(r, L·r база) {np.corrcoef(x.ra, x.L * x.rb)[0, 1]:+.2f}")
    # 3) SKHY / SKHYNIX
    print("\n3) SKHY (АДР, Nasdaq) / SKHYNIX (KRX): отношение цен перпов (часовые закрытия)")
    a, b = hourly(K, "SKHY"), hourly(K, "SKHYNIX")
    j = a.index.intersection(b.index)
    q = (a.loc[j] / b.loc[j])
    q = q[q.index >= int(datetime.datetime(2026, 7, 13, tzinfo=UTC).timestamp())]
    qd = q.groupby(pd.to_datetime(q.index, unit="s", utc=True).date).last()
    print(f"  отношение: медиана {q.median():.4f}, min {q.min():.4f}, max {q.max():.4f}; дневное изменение отношения "
          f"σ = {np.log(qd).diff().std() * 100:.2f}%")
    print("  по неделям (последнее значение): " + ", ".join(f"{d:%d.%m} {v:.4f}" for d, v in
                                                          qd.groupby(pd.to_datetime(qd.index).to_period('W')).last()
                                                          .rename(lambda p: p.start_time).items()))
    # 4) корейские в часы США
    print("\n4) Часовые изменения SKHYNIX/SAMSUNG vs полупроводники США (SOXL, MU, SNDK, SKHY) по сессиям KRX:")
    rk = {s: np.log(hourly(K, s)).diff() for s in ("SKHYNIX", "SAMSUNG", "SOXL", "MU", "SNDK", "SKHY")}
    for kr in ("SKHYNIX", "SAMSUNG"):
        for us in ("SOXL", "MU", "SNDK", "SKHY"):
            j = rk[kr].index.intersection(rk[us].index)
            j = j[(j >= int(datetime.datetime(2026, 7, 13, tzinfo=UTC).timestamp())) & (j < T_END)]
            kses = pd.Series(kr_session(np.asarray(j, dtype=np.int64) - 3600), index=j)
            uses = pd.Series(us_session(np.asarray(j, dtype=np.int64) - 3600), index=j)
            out = []
            for lab, m in (("KRX открыта", kses == "OPEN"), ("США REG", (uses == "REG") & (kses != "WKND")),
                           ("выходные", kses == "WKND")):
                x, y = rk[kr].loc[j][m.values], rk[us].loc[j][m.values]
                mm = np.isfinite(x.values) & np.isfinite(y.values)
                out.append(f"{lab}: {np.corrcoef(x.values[mm], y.values[mm])[0, 1]:+.2f} (n={int(mm.sum())})")
            print(f"  {kr:8s} ~ {us:5s} " + "; ".join(out))


if __name__ == "__main__":
    main()
