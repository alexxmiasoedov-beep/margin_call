"""Шорт после корейского листинга — разбор (kr_short.py): что из прибыли — общее падение альтов, как идёт цена после
открытия, какие фильтры известны в момент входа (без заглядывания вперёд) и как они держатся по половинам истории.

Рынок для сравнения — медиана доходности всех фьючерсов Binance за то же окно (шорт «средней монеты»).
Запуск из папки с данными: python3 s15/kr_short2.py"""
import os
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import BAR, K
from kr_short import events, run, stats

SYMS = list(K)


def market(t0, t1):
    """Медиана доходности шорта всех фьючерсов, у которых есть свечи в t0 и t1 (начала 15-мин свечей)."""
    r = []
    for s in SYMS:
        t = K[s]["t"]
        if t[0] > t0 or t[-1] < t1:
            continue
        i0, i1 = np.searchsorted(t, t0), np.searchsorted(t, t1)
        if t[i0] == t0 and t[i1] == t1 and K[s]["qv"][i0] > 0 and K[s]["qv"][i1] > 0:
            r.append(1 - float(K[s]["c"][i1]) / float(K[s]["c"][i0]))
    return float(np.median(r)) if len(r) > 50 else np.nan


def path(E, hours=(1, 2, 4, 8, 12, 24, 48, 72, 120, 168, 240, 336)):
    """Средняя доходность шорта (только цена, без стопа) через h часов после входа."""
    rows = []
    for e in E:
        x = run([e], hold_h=1, sl=None)
        if not len(x):
            continue
        s = x.sym.iloc[0]; a = K[s]; t = a["t"]
        j = int(np.searchsorted(t, e["t"], side="right")) - 1
        p0 = float(a["c"][j]); row = dict(t=e["t"], ex=e["ex"], second=e["second"])
        for h in hours:
            k = j + 4 * h
            row[h] = 1 - float(a["c"][k]) / p0 if k < len(t) and t[k] == t[j] + 4 * h * BAR else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    E = events()
    print("путь цены после открытия (шорт, только цена, без стопа и комиссии), среднее / медиана:")
    Pth = path(E)
    for name, m in (("все", np.ones(len(Pth), bool)), ("первый корейский листинг", ~Pth.second), ("второй", Pth.second)):
        g = Pth[m]
        print(f"  {name:26s} n={len(g)}: " + ", ".join(f"{h} ч {g[h].mean() * 100:+.1f}/{g[h].median() * 100:+.1f}" for h in (1, 4, 12, 24, 48, 72, 168, 336)))

    print("\nсравнение с рынком (выход по времени, без стопа): шорт монеты − шорт медианного фьючерса за то же окно")
    for hold in (48, 168):
        r = run(E, hold_h=hold, sl=None)
        r["mkt"] = [market(float(K[s]["t"][0]) * 0 + t0, t0 + hold * 3600) for s, t0 in
                    zip(r.sym, [float(np.floor(t / BAR) * BAR) for t in r.t])]
        r["ex_ret"] = r.price - r.mkt
        h = r.t < r.t.median()
        print(f"  {hold} ч: монета {r.price.mean() * 100:+.1f}%, рынок {r.mkt.mean() * 100:+.1f}%, разница {r.ex_ret.mean() * 100:+.1f}% "
              f"(медиана {r.ex_ret.median() * 100:+.1f}%, 1-я/2-я половина {r.ex_ret[h].mean() * 100:+.1f}/{r.ex_ret[~h].mean() * 100:+.1f}%)")

    print("\nфильтры, известные в момент входа (48 / 72 / 168 ч, стоп 25%; 168 ч — и со стопом 50%):")
    base = run(E)
    flt = {
        "все": lambda r: np.ones(len(r), bool),
        "второй корейский листинг": lambda r: r.second.values,
        "рост за сутки до открытия < 10%": lambda r: (r.pre24 < 0.10).values,
        "фьючерс старше 7 дней": lambda r: (r.age_d >= 7).values,
        "второй + фьючерс старше 7 дней": lambda r: (r.second & (r.age_d >= 7)).values,
        "второй + рост до открытия < 10%": lambda r: (r.second & (r.pre24 < 0.10)).values,
        "первый + рост до открытия < 10%": lambda r: (~r.second & (r.pre24 < 0.10)).values,
    }
    for kw_name, kw in (("48 ч", dict(hold_h=48)), ("72 ч", dict(hold_h=72)), ("168 ч", dict(hold_h=168)), ("168 ч, стоп 50%", dict(hold_h=168, sl=0.5))):
        r = run(E, **kw)
        print(f"  — {kw_name}")
        for nm, f in flt.items():
            print(f"    {nm:34s} {stats(r[f(r)])}")

    print("\nвход через 2 ч, если за 2 ч после открытия не было +15% от цены до открытия (48 ч, стоп 25%):")
    r2 = run(E, delay_h=2)
    ok = r2.pump2h < 0.15
    print(f"  без пампа: {stats(r2[ok])}\n  с пампом:  {stats(r2[~ok])}")

    print("\nхудшие 12 сделок (вход сразу, 48 ч, стоп 25%):")
    for x in base.sort_values("net").head(12).itertuples():
        print(f"  {pd.to_datetime(x.t, unit='s'):%d.%m.%Y %H:%M} {x.ex:7s} {x.base:10s} {x.net * 100:+6.1f}% ({x.why}), второй {x.second}, "
              f"обе {x.both}, фьючерсу {x.age_d:.0f} дн., рост до открытия {x.pre24 * 100:+.0f}%, памп 2 ч {x.pump2h * 100:+.0f}%")
