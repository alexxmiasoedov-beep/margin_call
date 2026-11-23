"""s263 — частоты событий для гипотез §10 во 2-й половине истории (06.09–19.11.2026). Считаются только события
(условие на прошлом и в момент входа), доходы после входа не считаются.

Запуск из /home/user/mc_data: python3 -I <путь>/freq_hyp.py"""
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
H0 = datetime.date(2026, 9, 6)
H1 = datetime.date(2026, 11, 19)
MON = ((H1 - H0).days + 1) / 30.4
T0 = int(datetime.datetime(2026, 9, 6, tzinfo=UTC).timestamp())
T1 = int(datetime.datetime(2026, 11, 20, tzinfo=UTC).timestamp())


def at_close(arr_t, arr_c, T):
    i = int(np.searchsorted(arr_t, T - 900))
    return float(arr_c[i]) if i < len(arr_t) and int(arr_t[i]) == T - 900 else np.nan


def main():
    K = load_k()
    I = pickle.load(open(f"{SHM}/bv_indexPriceKlines_15m.pkl", "rb"))
    meta = load_meta()
    meta = meta[meta.k_n > 0].copy()
    meta["grp"] = [group(s, u) for s, u in zip(meta.sym, meta.ut)]
    vol = pd.read_csv("s263/desc_volume_sym.csv").set_index("sym").qv30
    meta["q"] = meta.sym.map(vol).fillna(0)
    out = []

    def add(name, n, days, note=""):
        out.append((name, n / MON, days / MON, note))

    # Г1: открытие KRX, |ход перпа вне часов| ≥ 2% (из reopen_rows.pkl)
    R = pd.read_pickle(f"{SHM}/reopen_rows.pkl")
    kr = R[(R.key == "kr") & (R.te >= T0) & (R.te < T1)]
    liq_kr = set(meta.sym[(meta.grp == "KR_EQUITY") & (meta.q >= 2e7)])
    k1 = kr[kr.sym.isin(liq_kr) & (kr.M.abs() >= 0.02)]
    add("Г1 открытие KRX, |M| ≥ 2%, ликвидные корейские (" + ", ".join(sorted(liq_kr)) + ")", len(k1), k1.te.nunique())
    k2 = kr[(kr.M.abs() >= 0.02)]
    add("Г1 то же, все корейские перпы", len(k2), k2.te.nunique())
    # Г2, Г3: дни США — регулярная сессия по индексу (9:30 → 16:00 ET), ночной разрыв перпа (16:00 → 9:30 ET)
    us = meta[meta.grp.isin(["US_STOCK", "US_ETF", "US_LEV"]) & (meta.q >= 5e7)]
    rows = []
    d = H0
    while d <= H1:
        if d.weekday() < 5 and d.isoformat() not in NYSE_HOLI:
            o = int(datetime.datetime(d.year, d.month, d.day, 9, 30, tzinfo=NY).timestamp())
            c = int(datetime.datetime(d.year, d.month, d.day, 16, 0, tzinfo=NY).timestamp())
            prev = d - datetime.timedelta(1)
            while prev.weekday() >= 5 or prev.isoformat() in NYSE_HOLI:
                prev -= datetime.timedelta(1)
            pc = int(datetime.datetime(prev.year, prev.month, prev.day, 16, 0, tzinfo=NY).timestamp())
            for s in us.sym:
                if s not in I:
                    continue
                ia = I[s]
                i_o, i_c, i_pc = (at_close(ia[:, 0], ia[:, 4], T) for T in (o + 900, c, pc))
                p_o = at_close(K[s]["t"], K[s]["c"], o)
                rows.append(dict(sym=s, d=d, grp=us.grp[us.sym == s].iloc[0], day=i_c / i_o - 1 if i_o else np.nan,
                                 gap=p_o / i_pc - 1 if i_pc else np.nan))
        d += datetime.timedelta(1)
    U = pd.DataFrame(rows)
    # Г9: ночь будней США — ход перпа 20:00 → 4:00 ET (пн–чт вечер → вт–пт утро)
    rows9 = []
    d = H0
    while d <= H1:
        nd = d + datetime.timedelta(1)
        if d.weekday() < 4 and d.isoformat() not in NYSE_HOLI and nd.isoformat() not in NYSE_HOLI:
            A = int(datetime.datetime(d.year, d.month, d.day, 20, 0, tzinfo=NY).timestamp())
            B = int(datetime.datetime(nd.year, nd.month, nd.day, 4, 0, tzinfo=NY).timestamp())
            for s in us.sym:
                pa, pb = at_close(K[s]["t"], K[s]["c"], A), at_close(K[s]["t"], K[s]["c"], B)
                rows9.append(dict(sym=s, d=d, r=pb / pa - 1 if pa else np.nan))
        d += datetime.timedelta(1)
    N9 = pd.DataFrame(rows9)
    x = N9[N9.r.abs() >= 0.02]
    out.append(("Г9 ночь будней США: |ход перпа 20:00 → 4:00 ET| ≥ 2%, перпы ≥ 50 млн $/сут", len(x) / MON,
                x.d.nunique() / MON, f"медиана |ход| {N9.r.abs().median() * 100:.2f}%"))
    for thr in (0.03, 0.05):
        x = U[U.day.abs() >= thr]
        add(f"Г2 сильный день США (9:45→16:00 ET по индексу) |r| ≥ {thr:.0%}, перпы ≥ 50 млн $/сут", len(x), x.d.nunique())
    x = U[U.gap >= 0.02]
    add("Г3 ночной рост перпа к открытию США ≥ +2% (16:00 → 9:30 ET), ≥ 50 млн $/сут", len(x), x.d.nunique())
    x = U[U.gap <= -0.02]
    add("Г3′ ночное падение ≤ −2% (зеркало)", len(x), x.d.nunique())
    # Г6: открытие США у плечевых перпов — ход индекса за первые 15 мин ≥ 3%
    lev = R[(R.grp == "US_LEV") & (R.kind == "OPEN930") & (R.te >= T0) & (R.te < T1)]
    liq_lev = set(meta.sym[(meta.grp == "US_LEV") & (meta.q >= 2e7)])
    x = lev[lev.sym.isin(liq_lev) & (lev.J.abs() >= 0.03)]
    add("Г6 плечевые ETF: |ход за первые 15 мин после 9:30 ET| ≥ 3% (ликвидные)", len(x), x.te.nunique())
    # Г7: новые TradFi-перпы
    on = pd.to_datetime(meta.onboard, unit="s", utc=True).dt.date
    x = meta[(on >= H0) & (on <= H1)]
    add("Г7 запуск нового TradFi-перпа", len(x), x.onboard.map(lambda t: t // 86400).nunique())
    # Г8: выходные, |ход BTC| пт 20:00 → вс 19:45 ET ≥ 2%
    btc = K["BTC"]
    n_w, n_big = 0, 0
    d = H0
    while d <= H1:
        if d.weekday() == 4:
            A = int(datetime.datetime(d.year, d.month, d.day, 20, 0, tzinfo=NY).timestamp())
            sun = d + datetime.timedelta(2)
            B = int(datetime.datetime(sun.year, sun.month, sun.day, 19, 45, tzinfo=NY).timestamp())
            r = at_close(btc["t"], btc["c"], B) / at_close(btc["t"], btc["c"], A) - 1
            n_w += 1
            n_big += abs(r) >= 0.02
        d += datetime.timedelta(1)
    n_liq = int(((meta.grp.isin(["US_STOCK", "US_ETF", "US_LEV"])) & (meta.q >= 5e7)).sum())
    add(f"Г8 выходные с |ход BTC| ≥ 2% × {n_liq} ликвидных перпов (выходных {n_big} из {n_w})", n_big * n_liq, n_big)
    # Г5: дивидендные спецначисления (без ежедневных STRC)
    sp = pd.read_csv("s263/dividend_special_funding.csv")
    sp = sp[(sp.t >= T0) & (sp.t < T1) & (sp.sym != "STRC")]
    add("Г5 дивидендное спецначисление (без STRC)", len(sp), (sp.t // 86400).nunique(),
        f"медиана {sp.rate.median() * 100:.2f}%")
    # Г4: отчётности
    try:
        E = pd.read_csv("s263/calendar_earnings.csv")
        E["d"] = pd.to_datetime(E.date).dt.date
        E = E[(E.d >= H0) & (E.d <= H1)]
        first = dict(zip(meta.sym, meta.k_first))
        E = E[[first.get(s, 9e18) <= int(datetime.datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp())
               for s, d in zip(E.sym, E.d)]]
        liq = set(meta.sym[meta.q >= 5e7])
        add("Г4 отчётность компании с перпом (все)", len(E), E.d.nunique(), str(E.time.value_counts().to_dict()))
        add("Г4 отчётность компании с перпом ≥ 50 млн $/сут", int(E.sym.isin(liq).sum()), E[E.sym.isin(liq)].d.nunique())
        E["m"] = pd.to_datetime(E.date).dt.strftime("%Y-%m")
        print("отчётности по месяцам (все с перпом):", E.groupby("m").size().to_dict())
    except FileNotFoundError:
        print("нет календаря отчётностей")
    D = pd.DataFrame(out, columns=["гипотеза/событие", "в месяц", "дней в месяц", "заметка"])
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 120)
    print(f"2-я половина истории {H0} – {H1} ({MON:.2f} мес.)")
    print(D.round(1).to_string(index=False))
    D.to_csv("s263/hyp_frequencies.csv", index=False)


if __name__ == "__main__":
    main()
