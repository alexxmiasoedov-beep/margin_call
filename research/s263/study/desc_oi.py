"""s263 — открытый интерес и позиции толпы по сессиям (метрики архива Binance, шаг 5 мин; fetch_metrics.py):
изменение OI за сессию (пт закрытие → вс открытие, в будни по сессиям США), OI к суточному обороту, доля счетов
в лонге (acc_ls) и отношение покупок тейкеров (taker_ls) по сессиям; OI вокруг открытия США и открытия ночной
сессии после выходных. Доходов не считает.

Запуск из /home/user/mc_data: python3 -I <путь>/desc_oi.py"""
import datetime
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common263 import SHM, UTC, cme_session, group, kr_session, load_k, load_meta, us_session  # noqa: E402


def main():
    M = pickle.load(open(f"{SHM}/metrics.pkl", "rb"))
    meta = load_meta().set_index("sym")
    K = load_k()
    rows = []
    for s, df in M.items():
        if not len(df):
            continue
        g = group(s, meta.ut[s])
        fn = {"COMMODITY": cme_session, "KR_EQUITY": kr_session}.get(g, us_session)
        df = df.sort_values("t").drop_duplicates("t").copy()
        df = df[df.t % 900 == 0]                       # шаг 15 мин, чтобы сессии считались как у свечей
        df["ses"] = fn(df.t.values)
        df["sym"], df["grp"] = s, g
        # суточный оборот перпа за последние 30 сут
        a = K[s]; t_end = int(a["t"][-1])
        q30 = float(a["qv"][a["t"] >= t_end - 30 * 86400].sum()) / 30
        df["q30"] = q30
        rows.append(df)
    D = pd.concat(rows, ignore_index=True)
    D = D[D.oi > 0]
    D["d_oi"] = D.groupby("sym").oi.pct_change().replace([np.inf, -np.inf], np.nan).clip(-0.5, 0.5)
    last = D[D.t >= D.t.max() - 30 * 86400]
    print(f"символов с метриками: {D.sym.nunique()}; строк {len(D):,}")
    print("\nOI к суточному обороту (последние 30 сут), медиана по символам по группам:")
    r = last.groupby(["grp", "sym"]).agg(oi=("oi_usd", "median"), q=("q30", "first"))
    r["ratio"] = r.oi / r.q
    print(r.groupby(level=0).ratio.describe()[["count", "50%", "min", "max"]].round(2).to_string())
    print("\nПо сессиям (все символы, медианы по символам): изменение OI за 15 мин (б. п.), доля счетов в лонге acc_ls,"
          " отношение покупок тейкеров taker_ls")
    x = D.groupby(["grp", "ses", "sym"]).agg(doi=("d_oi", "mean"), acc=("acc_ls", "median"), tak=("taker_ls", "median"),
                                              top=("top_pos_ls", "median"))
    y = x.groupby(level=[0, 1]).median()
    y["doi"] = y.doi * 1e4
    print(y.round(3).to_string())
    # OI за выходные: пт 20:00 ET → вс 20:00 ET (акции), пт 17:00 → вс 18:00 ET (сырьё)
    print("\nИзменение OI за выходные (медиана по символам и выходным, %) и за будние ночи (пн–чт 20:00 → 9:30 ET):")
    from zoneinfo import ZoneInfo
    NY = ZoneInfo("America/New_York")
    out = []
    for s, df in D.groupby("sym"):
        g = df.grp.iloc[0]
        ser = df.set_index("t").oi
        d = datetime.date(2026, 7, 3)
        while d <= datetime.date(2026, 11, 13):
            if d.weekday() == 4:
                if g == "COMMODITY":
                    a_, b_ = (datetime.datetime(d.year, d.month, d.day, 17, 0, tzinfo=NY),
                              datetime.datetime(d.year, d.month, d.day, 18, 0, tzinfo=NY) + datetime.timedelta(2))
                else:
                    a_, b_ = (datetime.datetime(d.year, d.month, d.day, 20, 0, tzinfo=NY),
                              datetime.datetime(d.year, d.month, d.day, 20, 0, tzinfo=NY) + datetime.timedelta(2))
                A, B = int(a_.timestamp()), int(b_.timestamp())
                if A in ser.index and B in ser.index and ser[A] > 0:
                    out.append(dict(sym=s, grp=g, kind="выходные", ch=ser[B] / ser[A] - 1))
            if d.weekday() < 4 and g != "COMMODITY":
                a_ = datetime.datetime(d.year, d.month, d.day, 20, 0, tzinfo=NY)
                b_ = datetime.datetime(d.year, d.month, d.day, 9, 30, tzinfo=NY) + datetime.timedelta(1)
                A, B = int(a_.timestamp()), int(b_.timestamp())
                if A in ser.index and B in ser.index and ser[A] > 0:
                    out.append(dict(sym=s, grp=g, kind="ночь будней", ch=ser[B] / ser[A] - 1))
                a2 = datetime.datetime(d.year, d.month, d.day, 9, 30, tzinfo=NY)
                b2 = datetime.datetime(d.year, d.month, d.day, 16, 0, tzinfo=NY)
                A, B = int(a2.timestamp()), int(b2.timestamp())
                if A in ser.index and B in ser.index and ser[A] > 0:
                    out.append(dict(sym=s, grp=g, kind="день США", ch=ser[B] / ser[A] - 1))
            d += datetime.timedelta(1)
    O = pd.DataFrame(out)
    print((O.groupby(["grp", "kind"]).ch.agg(["median", "mean", "size"]) * [100, 100, 1]).round(2).to_string())
    print("\nДоля выходных, когда OI вырос, по группам:")
    print(O[O.kind == "выходные"].groupby("grp").ch.apply(lambda v: (v > 0).mean()).round(2).to_string())


if __name__ == "__main__":
    main()
