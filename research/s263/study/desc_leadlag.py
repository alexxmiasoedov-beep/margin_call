"""s263 — кто ведёт цену: минутные свечи перпа (klines 1m) и индекса (indexPriceKlines 1m) за 10.2026 у 15 символов.
Для каждой сессии базового рынка — корреляции минутных изменений перпа и индекса со сдвигом −5…+5 мин
(сдвиг > 0: перп раньше индекса). Доля «опережения» = сумма корреляций при сдвигах > 0 / (сумма при < 0 + при > 0).
Это описание связи двух рядов, не доход сделок.

Запуск из /home/user/mc_data: python3 -I <путь>/desc_leadlag.py"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common263 import SHM, cme_session, hk_session, kr_session, us_session  # noqa: E402

FN = {"XAU": cme_session, "XAG": cme_session, "CL": cme_session, "SKHYNIX": kr_session, "SAMSUNG": kr_session,
      "TENCENT": hk_session}
LAGS = range(-5, 6)


def main():
    P = pickle.load(open(f"{SHM}/bv_klines_1m.pkl", "rb"))
    I = pickle.load(open(f"{SHM}/bv_indexPriceKlines_1m.pkl", "rb"))
    out = []
    for s in sorted(set(P) & set(I)):
        p = pd.Series(P[s][:, 4], index=P[s][:, 0].astype(np.int64))
        i = pd.Series(I[s][:, 4], index=I[s][:, 0].astype(np.int64))
        j = p.index.intersection(i.index)
        p, i = p.loc[j].sort_index(), i.loc[j].sort_index()
        rp, ri = np.log(p).diff(), np.log(i).diff()
        ses = pd.Series((FN.get(s, us_session))(np.asarray(j, dtype=np.int64)), index=j)
        for sname in sorted(set(ses)):
            m = (ses == sname).values
            if m.sum() < 500:
                continue
            cs = {}
            for L in LAGS:
                # L > 0: изменение перпа в t сопоставляется с изменением индекса в t + L
                a = rp.values
                b = ri.shift(-L).values
                mm = m & np.isfinite(a) & np.isfinite(b)
                cs[L] = np.corrcoef(a[mm], b[mm])[0, 1] if mm.sum() > 100 and np.std(a[mm]) > 0 and np.std(b[mm]) > 0 else np.nan
            lead = np.nansum([max(cs[L], 0) for L in LAGS if L > 0])
            lag = np.nansum([max(cs[L], 0) for L in LAGS if L < 0])
            vr = np.nanstd(rp.values[m]) / np.nanstd(ri.values[m]) if np.nanstd(ri.values[m]) > 0 else np.nan
            out.append(dict(sym=s, ses=sname, n=int(m.sum()), c0=cs[0], c1=cs[1], cm1=cs[-1], c2=cs[2], cm2=cs[-2],
                            lead_share=lead / (lead + lag) if lead + lag > 0 else np.nan, vol_ratio=vr))
    D = pd.DataFrame(out)
    D.to_csv("s263/leadlag_1m.csv", index=False)
    pd.set_option("display.width", 200)
    print("Корреляции минутных изменений перпа (t) и индекса (t + сдвиг), октябрь 2026; lead_share > 0,5 — перп раньше;"
          " vol_ratio — σ минутных изменений перпа / индекса")
    print(D.round(3).to_string(index=False))
    switches(P, I)


def switches(P, I):
    """Минуты смены режима индекса: |изменение индекса| в первые 3 мин после смены против медианы |изменения| за
    30 мин до неё (во сколько раз), и тот же показатель у перпа. Показывает, где индекс «прыгает» к внешней цене."""
    from zoneinfo import ZoneInfo
    NY = ZoneInfo("America/New_York")
    SEO = ZoneInfo("Asia/Seoul")
    HKT = ZoneInfo("Asia/Hong_Kong")
    rows = []
    for s in sorted(set(P) & set(I)):
        pi = pd.Series(I[s][:, 4], index=I[s][:, 0].astype(np.int64))
        pp = pd.Series(P[s][:, 4], index=P[s][:, 0].astype(np.int64))
        for day in range(1, 32):
            try:
                d = pd.Timestamp(2026, 10, day)
            except ValueError:
                continue
            cands = []
            if s in ("SKHYNIX", "SAMSUNG"):
                if d.weekday() < 5:
                    cands.append(("KRX 09:00 KST", pd.Timestamp(2026, 10, day, 9, 0, tz=SEO)))
                    cands.append(("KRX 15:20 KST", pd.Timestamp(2026, 10, day, 15, 20, tz=SEO)))
            elif s == "TENCENT":
                if d.weekday() < 5:
                    cands.append(("HKEX 09:30", pd.Timestamp(2026, 10, day, 9, 30, tz=HKT)))
                    cands.append(("HKEX 16:00", pd.Timestamp(2026, 10, day, 16, 0, tz=HKT)))
            elif s in ("XAU", "XAG", "CL"):
                if d.weekday() == 6:
                    cands.append(("CME вс 18:00 ET", pd.Timestamp(2026, 10, day, 18, 0, tz=NY)))
                if d.weekday() < 4:
                    cands.append(("CME 18:00 ET будни", pd.Timestamp(2026, 10, day, 18, 0, tz=NY)))
                if d.weekday() == 4:
                    cands.append(("CME пт 17:00 ET", pd.Timestamp(2026, 10, day, 17, 0, tz=NY)))
            else:
                if d.weekday() < 5:
                    for lab, hh, mm in (("США 4:00 ET", 4, 0), ("США 9:30 ET", 9, 30), ("США 16:00 ET", 16, 0)):
                        cands.append((lab, pd.Timestamp(2026, 10, day, hh, mm, tz=NY)))
                    if d.weekday() < 4:
                        cands.append(("США 20:00 ET (пн–чт)", pd.Timestamp(2026, 10, day, 20, 0, tz=NY)))
                    if d.weekday() == 4:
                        cands.append(("США пт 20:00 ET", pd.Timestamp(2026, 10, day, 20, 0, tz=NY)))
                if d.weekday() == 6:
                    cands.append(("США вс 20:00 ET", pd.Timestamp(2026, 10, day, 20, 0, tz=NY)))
            for lab, T in cands:
                t = int(T.timestamp())
                pre_i = pi.loc[t - 1800:t - 60].diff().abs()
                pre_p = pp.loc[t - 1800:t - 60].diff().abs()
                if len(pre_i) < 20 or (t + 180) not in pi.index or (t - 60) not in pi.index:
                    continue
                ji = abs(pi[t + 180] / pi[t - 60] - 1)
                jp = abs(pp.get(t + 180, np.nan) / pp.get(t - 60, np.nan) - 1)
                base_i = float((pre_i / pi.loc[t - 1800:t - 60]).median()) * np.sqrt(4)
                base_p = float((pre_p / pp.loc[t - 1800:t - 60]).median()) * np.sqrt(4)
                rows.append(dict(sym=s, ev=lab, ji=ji, jp=jp, ri=ji / base_i if base_i > 0 else np.nan,
                                 rp=jp / base_p if base_p > 0 else np.nan))
    R = pd.DataFrame(rows)
    print("\nСмена режима индекса (октябрь 2026): медианы |изменения| за 4 мин (−1…+3) у индекса и перпа, б. п.,"
          " и во сколько раз это больше обычного (медиана |минутного изменения| за 30 мин до × √4)")
    g = R.groupby("ev").agg(n=("ji", "size"), ji=("ji", "median"), jp=("jp", "median"), ri=("ri", "median"),
                            rp=("rp", "median"))
    g["ji"] *= 1e4
    g["jp"] *= 1e4
    print(g.round(1).to_string())


if __name__ == "__main__":
    main()
