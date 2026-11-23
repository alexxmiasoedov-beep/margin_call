"""s263 — частоты событий по расписанию для TradFi-перпов во 2-й половине истории (06.09–19.11.2026; медиана
символо-суток всех TradFi-перпов — 06.09.2026). Событие считается «символ × момент», если у символа живой перп
(оборот за последние 30 сут ≥ 20 млн $ в сутки для «ликвидных» строк). Доходов не считает.

Запуск из /home/user/mc_data: python3 -I <путь>/desc_events.py"""
import datetime
import json
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common263 import LEV, NYSE_HOLI, UTC, group, load_k, load_meta  # noqa: E402

NY = ZoneInfo("America/New_York")
H0 = datetime.date(2026, 9, 6)
H1 = datetime.date(2026, 11, 19)
MONTHS = ((H1 - H0).days + 1) / 30.4
KRX_HOLI = {"2026-09-24", "2026-09-25", "2026-10-05", "2026-10-09"}
HK_HOLI = {"2026-10-01", "2026-10-19"}


def alive(meta, d):
    t = int(datetime.datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp())
    return meta[(meta.k_first <= t - 3 * 86400)]


def main():
    meta = load_meta()
    meta = meta[meta.k_n > 0].copy()
    meta["grp"] = [group(s, u) for s, u in zip(meta.sym, meta.ut)]
    vol = pd.read_csv("s263/desc_volume_sym.csv").set_index("sym").qv30
    meta["liq"] = meta.sym.map(vol).fillna(0) >= 2e7
    K = load_k()
    out = []

    def add(kind, n_events, n_days, note=""):
        out.append(dict(kind=kind, per_month=n_events / MONTHS, days_per_month=n_days / MONTHS, note=note))

    days = [H0 + datetime.timedelta(i) for i in range((H1 - H0).days + 1)]
    us_td = [d for d in days if d.weekday() < 5 and d.isoformat() not in NYSE_HOLI]
    sundays = [d for d in days if d.weekday() == 6 and (d + datetime.timedelta(1)).isoformat() not in NYSE_HOLI]
    kr_td = [d for d in days if d.weekday() < 5 and d.isoformat() not in KRX_HOLI]
    hk_td = [d for d in days if d.weekday() < 5 and d.isoformat() not in HK_HOLI]
    us_grp = {"US_STOCK", "US_ETF", "US_LEV"}

    def cnt(dl, cond):
        n = 0
        for d in dl:
            a = alive(meta, d)
            n += int(cond(a).sum())
        return n
    add("Открытие США 9:30 ET (ликвидные акции и фонды)", cnt(us_td, lambda a: a.grp.isin(us_grp) & a.liq), len(us_td))
    add("Открытие США 9:30 ET (все акции и фонды)", cnt(us_td, lambda a: a.grp.isin(us_grp)), len(us_td))
    add("Закрытие США 16:00 ET — ребаланс плечевых ETF (ликвидные)", cnt(us_td, lambda a: (a.grp == "US_LEV") & a.liq),
        len(us_td))
    add("Выходные США: открытие ночной сессии вс 20:00 ET (ликвидные)", cnt(sundays, lambda a: a.grp.isin(us_grp) & a.liq),
        len(sundays))
    add("Выходные CME: вс 18:00 ET (сырьё)", cnt([d for d in days if d.weekday() == 6], lambda a: a.grp == "COMMODITY"),
        sum(d.weekday() == 6 for d in days))
    add("CME: открытие после перерыва 18:00 ET пн–чт (сырьё)", cnt([d for d in days if d.weekday() < 4],
                                                                   lambda a: a.grp == "COMMODITY"),
        sum(d.weekday() < 4 for d in days))
    add("Открытие KRX 09:00 KST (корейские, ликвидные)", cnt(kr_td, lambda a: (a.grp == "KR_EQUITY") & a.liq), len(kr_td))
    add("Открытие KRX 09:00 KST (все корейские)", cnt(kr_td, lambda a: a.grp == "KR_EQUITY"), len(kr_td))
    add("Открытие HKEX 09:30 HKT (все гонконгские)", cnt(hk_td, lambda a: a.grp == "HK_EQUITY"), len(hk_td))
    add("Праздники NYSE (полный день) × ликвидные акции", cnt([d for d in days if d.isoformat() in NYSE_HOLI],
                                                              lambda a: a.grp.isin(us_grp) & a.liq),
        sum(d.isoformat() in NYSE_HOLI for d in days), "07.09, 26.11")
    add("Праздники KRX в будни × корейские", cnt([d for d in days if d.isoformat() in KRX_HOLI],
                                                 lambda a: a.grp == "KR_EQUITY"),
        sum(d.isoformat() in KRX_HOLI for d in days), ", ".join(sorted(KRX_HOLI)))
    # отчётности
    try:
        E = pd.read_csv("s263/calendar_earnings.csv")
        E["d"] = pd.to_datetime(E.date).dt.date
        on = dict(zip(meta.sym, meta.k_first))
        E = E[[(on.get(s, 9e18) <= int(datetime.datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp()))
               for s, d in zip(E.sym, E.d)]]
        Eh = E[(E.d >= H0) & (E.d <= H1)]
        liq = set(meta.sym[meta.liq])
        add("Отчётности компаний с перпом (все)", len(Eh), Eh.d.nunique(),
            "время: " + ", ".join(f"{k}: {v}" for k, v in Eh.time.value_counts().items()))
        add("Отчётности компаний с ликвидным перпом", int(Eh.sym.isin(liq).sum()), Eh[Eh.sym.isin(liq)].d.nunique())
        wk = Eh[pd.to_datetime(Eh.date).dt.weekday == 4]
        add("…из них в пятницу (реакция в выходные)", len(wk), wk.d.nunique())
    except FileNotFoundError:
        print("нет календаря отчётностей")
    # дивиденды: по фандингу (внеочередные начисления) и по календарю Nasdaq
    dv = pd.read_csv("s263/dividend_funding_events.csv")
    dv["d"] = pd.to_datetime(dv.t, unit="s", utc=True).dt.date
    dvh = dv[(dv.d >= H0) & (dv.d <= H1)]
    add("Дивидендные начисления в фандинге (обнаружены по часовому интервалу)", len(dvh), dvh.d.nunique(),
        f"медиана ставки {dvh.rate.median() * 100:.2f}%")
    try:
        C = pd.read_csv("s263/calendar_dividends.csv")
        C["d"] = pd.to_datetime(C.ex, format="%m/%d/%Y", errors="coerce").dt.date
        C = C[(C.d >= H0) & (C.d <= H1)].drop_duplicates(["sym", "d"])
        on = dict(zip(meta.sym, meta.k_first))
        C = C[[on.get(s, 9e18) <= int(datetime.datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp()) for s, d in zip(C.sym, C.d)]]
        add("Экс-дивидендные даты по календарю Nasdaq (тикеры с перпом)", len(C), C.d.nunique(),
            f"из них плечевые/без компенсации: {int(C.sym.isin(LEV).sum())}")
    except FileNotFoundError:
        print("нет календаря дивидендов")
    # листинги TradFi-перпов
    lst = pd.to_datetime(meta.onboard, unit="s", utc=True).dt.date
    add("Новые TradFi-перпы на Binance (запуск)", int(((lst >= H0) & (lst <= H1)).sum()),
        len(set(lst[(lst >= H0) & (lst <= H1)])))
    # Pre-IPO
    A = json.load(open("s263/ann_tradfi.json"))
    pre = [a for a in A if "Pre-IPO" in a["title"]]
    add("Объявления Pre-IPO (запуск, смена размера, переход) — за всю историю", len(pre), len(pre),
        "; ".join(a["title"][:60] for a in pre[-3:]))
    D = pd.DataFrame(out)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 90)
    print(f"2-я половина истории: {H0} – {H1} ({MONTHS:.2f} мес.)")
    print(D.round(1).to_string(index=False))
    D.to_csv("s263/event_frequencies.csv", index=False)
    # проверка праздников KRX по обороту корейских перпов в 00–06 UTC (будни)
    print("\nОборот корейских перпов 00:00–06:20 UTC по будням (млн $; низкий — KRX закрыта):")
    ks = list(meta.sym[meta.grp == "KR_EQUITY"])
    rows = []
    for d in days:
        if d.weekday() >= 5:
            continue
        t0 = int(datetime.datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp())
        q = 0.0
        for s in ks:
            a = K[s]; m = (a["t"] >= t0) & (a["t"] < t0 + 6 * 3600 + 1200)
            q += float(a["qv"][m].sum())
        rows.append((d.isoformat(), q / 1e6))
    R = pd.DataFrame(rows, columns=["d", "q"])
    med = R.q.median()
    print("  медиана", round(med), "; дни < 40% медианы:", ", ".join(f"{d} ({q:.0f})" for d, q in R[R.q < 0.4 * med].values))


if __name__ == "__main__":
    main()
