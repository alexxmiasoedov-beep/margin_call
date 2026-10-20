import datetime, numpy as np, pandas as pd
MSK = datetime.timezone(datetime.timedelta(hours=3))
D = pd.read_pickle("mm/short_scan.pkl")
M0 = datetime.datetime(2026, 9, 19, tzinfo=MSK).timestamp(); M1 = datetime.datetime(2026, 10, 17, tzinfo=MSK).timestamp()
V0 = datetime.datetime(2026, 4, 8, tzinfo=MSK).timestamp(); V1 = datetime.datetime(2026, 9, 18, tzinfo=MSK).timestamp()
def trades(x):
    """Одна сделка на монету, следующая — не раньше чем через сутки (сделка длится до 24 ч)."""
    x = x.sort_values("te"); out, last = [], {}
    for r in x.itertuples():
        if r.te - last.get(r.sym, -1e18) >= 86400: out.append(r.pnl); last[r.sym] = r.te
    return np.array(out)
def show(mask, lab):
    res = []
    for a, b in ((M0, M1), (V0, V1)):
        tr = trades(D[mask & (D.te >= a) & (D.te < b)])
        res.append(f"{len(tr):5d} сд. {tr.mean()*100 if len(tr) else 0:+5.2f}% (тейк {np.mean(tr > 0.14)*100 if len(tr) else 0:3.0f}%, стоп {np.mean(tr < -0.09)*100 if len(tr) else 0:3.0f}%)")
    print(f"  {lab:52s} месяц: {res[0]} | полгода до: {res[1]}")
T = pd.Series(True, index=D.index)
print("Шорт после пампа ≥ 30% за сутки; тейк −15% / стоп +10% / 24 ч. Месяц 19.09–17.10 (поиск) | 08.04–18.09 (проверка)")
show(T, "все моменты после пампа")
print("Насколько цена уже ниже максимума:")
for a, b, lab in ((-0.03, 0.01, "0…−3%"), (-0.07, -0.03, "−3…−7%"), (-0.12, -0.07, "−7…−12%"), (-0.20, -0.12, "−12…−20%"), (-1, -0.20, "ниже −20%")):
    show((D.from_top > a) & (D.from_top <= b), f"  от максимума {lab}")
print("Сколько часов без нового максимума:")
for a, b in ((0, 1), (1, 3), (3, 8), (8, 24)):
    show((D.h_since >= a) & (D.h_since < b), f"  {a}–{b} ч")
print("Угасание объёма (последний час к часу вершины):")
for a, b, lab in ((0, 0.3, "< 0,3"), (0.3, 0.7, "0,3–0,7"), (0.7, 99, "≥ 0,7")):
    show((D.vol_fade >= a) & (D.vol_fade < b), f"  {lab}")
show(D.wick >= 0.5, "длинная верхняя тень на вершине (≥ половины свечи)")
show((D.lower_high <= -0.03) & (D.h_since >= 2), "неудачная вторая попытка: максимум 2 ч ниже вершины ≥ 3%")
show(D.ret_1h < -0.03, "сейчас падает: за час −3% и ниже")
show(D.ret_1h > 0.03, "сейчас растёт: за час +3% и выше")
show(D.inch, "в маржинальном канале за 4 ч")
for a, b in ((0.3, 0.5), (0.5, 1.0), (1.0, 99)):
    show((D.rise >= a) & (D.rise < b), f"рост пампа {int(a*100)}–{int(b*100) if b < 9 else '…'}%")
print("\nВнутри маржинального канала (монета в постах за 4 ч):")
C = D.inch
show(C, "в канале — все")
for a, b, lab in ((-0.07, 0.01, "0…−7%"), (-0.15, -0.07, "−7…−15%"), (-1, -0.15, "ниже −15%")):
    show(C & (D.from_top > a) & (D.from_top <= b), f"  + от максимума {lab}")
for a, b in ((0, 2), (2, 8), (8, 24)):
    show(C & (D.h_since >= a) & (D.h_since < b), f"  + {a}–{b} ч без нового максимума")
show(C & (D.vol_fade >= 0.7), "  + объём не угас (≥ 0,7 от вершины)")
show(C & (D.vol_fade < 0.7), "  + объём угас (< 0,7)")
show(C & (D.ret_1h > 0.03), "  + за час растёт ≥ 3%")
show(C & (D.ret_1h <= 0.03), "  + за час не растёт")
show(C & (D.rise < 0.5), "  + памп 30–50%")
show(C & (D.rise >= 0.5), "  + памп ≥ 50%")
