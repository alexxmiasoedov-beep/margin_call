"""s263 — внутридневной профиль по времени Нью-Йорка (будни, с 01.06.2026): доля оборота и средний |ход| перпа
за 15 мин, медиана |премии| — для акций, фондов и плечевых ETF; плюс корейские перпы по времени Сеула.
Показывает всплески на 4:00, 9:30, 16:00, 20:00 ET (смены сессий) и у закрытия (ребаланс плечевых ETF). Доходов нет.

Запуск из /home/user/mc_data: python3 -I <путь>/desc_intraday.py"""
import datetime
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common263 import NYSE_HOLI, SEOUL, SHM, UTC, NY, group, load_k, load_meta  # noqa: E402

T0 = int(datetime.datetime(2026, 6, 1, tzinfo=UTC).timestamp())
T1 = int(datetime.datetime(2026, 11, 20, tzinfo=UTC).timestamp())


def main():
    K = load_k()
    meta = load_meta()
    meta = meta[meta.k_n > 0].copy()
    meta["grp"] = [group(s, u) for s, u in zip(meta.sym, meta.ut)]
    vol = pd.read_csv("s263/desc_volume_sym.csv").set_index("sym").qv30
    P = pd.read_pickle(f"{SHM}/premium_rows.pkl")
    P = P[(P.t >= T0) & (P.t < T1)]
    for g, tz, lab in (("US_STOCK", NY, "ET"), ("US_LEV", NY, "ET"), ("US_ETF", NY, "ET"), ("KR_EQUITY", SEOUL, "KST")):
        syms = [s for s in meta.sym[meta.grp == g] if vol.get(s, 0) >= 2e7]
        frames = []
        for s in syms:
            a = K[s]
            m = (a["t"] >= T0) & (a["t"] < T1)
            t = a["t"][m]
            c = a["c"][m].astype(float)
            r = np.abs(np.diff(np.log(c), prepend=np.nan))
            idx = pd.to_datetime(t, unit="s", utc=True).tz_convert(tz)
            df = pd.DataFrame(dict(t=t, qv=a["qv"][m].astype(float), r=r, d=idx.strftime("%Y-%m-%d"), wd=idx.weekday,
                                   slot=idx.hour * 60 + idx.minute))
            df = df[(df.wd < 5) & ~df.d.isin(NYSE_HOLI if tz is NY else set())]
            df["share"] = df.qv / df.groupby("d").qv.transform("sum")
            df["sym"] = s
            frames.append(df)
        D = pd.concat(frames)
        pr = P[P.sym.isin(syms)].copy()
        pidx = pd.to_datetime(pr.t, unit="s", utc=True).dt.tz_convert(tz)
        pr["slot"] = pidx.dt.hour * 60 + pidx.dt.minute
        pr = pr[pidx.dt.weekday < 5]
        prem = pr.groupby("slot").p.apply(lambda v: v.abs().mean() * 1e4)
        prof = D.groupby("slot").agg(share=("share", "mean"), r=("r", "median"))
        prof["share"] *= 100
        prof["r"] *= 1e4
        prof["prem"] = prem
        print(f"\n{g}: {len(syms)} ликвидных символов; по 15-мин слотам ({lab}): доля суточного оборота %, медиана |ход| б. п.,"
              f" средняя |премия| б. п. (показаны слоты с особенностями и каждый час)")
        for sl, row in prof.iterrows():
            hh, mm = divmod(int(sl), 60)
            show = mm == 0 or (tz is NY and sl in (4 * 60, 9 * 60 + 15, 9 * 60 + 30, 9 * 60 + 45, 15 * 60 + 30, 15 * 60 + 45,
                                                       16 * 60, 16 * 60 + 15, 19 * 60 + 45, 20 * 60, 20 * 60 + 15)) \
                or (tz is SEOUL and sl in (8 * 60 + 45, 9 * 60, 9 * 60 + 15, 15 * 60, 15 * 60 + 15, 15 * 60 + 30))
            if show:
                print(f"  {hh:02d}:{mm:02d}  оборот {row.share:5.2f}%  |ход| {row.r:6.1f}  |P| {row.prem:5.2f}")


if __name__ == "__main__":
    main()
