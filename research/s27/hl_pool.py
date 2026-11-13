"""s27 — пулы трейдеров Hyperliquid на 1-е число каждого месяца только по прошлому (s27/pf/: история PnL и стоимости счёта)
и проверка Г0 «мастерство устойчиво». PnL за окно — разность накопленного PnL (линейная интерполяция по точкам истории).
Допуск: стоимость счёта ≥ $10 тыс. на дату, история началась хотя бы за 7 сут до даты (счёт моложе 90 сут — PnL с первой
точки). История portfolio у Hyperliquid хранится с 01.05.2024 — пулы с 01.08.2024.
Пулы по 100 счетов: top — лучшие по PnL за 90 сут (> 0); roi — лучшие по PnL к средней стоимости счёта; bottom — худшие;
rand (плацебо) — постоянные 300 случайных счетов, допущенных хотя бы в 3 месяцах; в месяце — допущенные из них. Кандидаты — первые N (по умолчанию 5000) в случайном порядке hl_fetch.candidates(). Итог — s27/pools.pkl: {месяц: {пул: [адреса]}} и s27/union.txt (все адреса пулов).
Запуск из папки с данными."""
import glob
import json
import os
import pickle
import random
import sys
import numpy as np, pandas as pd

DAY = 86400
MONTHS = pd.date_range("2024-08-01", "2026-11-01", freq="MS", tz="UTC")    # история portfolio — с 01.05.2024


NPOOL = 100


def load(n=5000):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from hl_fetch import candidates
    want = set(candidates()[:n])
    A = {}
    for f in glob.glob("s27/pf/*.json"):
        if os.path.basename(f)[:-5] not in want:
            continue
        d = json.load(open(f))
        if len(d["pnl"]) < 3:
            continue
        p = np.array([(x[0] / 1000, float(x[1])) for x in d["pnl"]])
        v = np.array([(x[0] / 1000, float(x[1])) for x in d["av"]]) if d["av"] else None
        A[os.path.basename(f)[:-5]] = (p, v)
    return A


def at(s, t):
    """Накопленный PnL в момент t (до первой точки — 0)."""
    if t <= s[0, 0]:
        return 0.0
    return float(np.interp(t, s[:, 0], s[:, 1]))


def table(A):
    rows = []
    for a, (p, v) in A.items():
        t0, t1 = p[0, 0], p[-1, 0]
        for D in MONTHS:
            d = D.timestamp()
            if d < t0 + 7 * DAY or d > t1:
                continue
            av = float(np.interp(d, v[:, 0], v[:, 1])) if v is not None else np.nan
            w0 = max(d - 90 * DAY, t0)
            pnl90 = at(p, d) - at(p, w0)
            avm = float(np.mean(np.interp(np.linspace(w0, d, 10), v[:, 0], v[:, 1]))) if v is not None else np.nan
            nxt = D + pd.offsets.MonthBegin(1)
            fut = at(p, min(nxt.timestamp(), t1)) - at(p, d) if nxt.timestamp() <= t1 + 3 * DAY else np.nan
            rows.append(dict(a=a, m=D, av=av, pnl90=pnl90, roi90=pnl90 / max(avm, 1e3), fut=fut))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    A = load(int(sys.argv[1]) if len(sys.argv) > 1 else 5000)
    T = table(A)
    print(f"счетов с историей: {len(A)}; строк счёт×месяц: {len(T)}")
    E = T[(T.av >= 1e4) & (T.pnl90 != 0)]
    print("\nГ0 — мастерство устойчиво? (допущенные: счёт ≥ $10 тыс.)")
    rs = []
    for m, x in E.groupby("m"):
        x = x.dropna(subset=["fut"])
        if len(x) < 100:
            continue
        rc = x.pnl90.rank().corr(x.fut.rank())
        rr = x.roi90.rank().corr((x.fut / x.av.clip(lower=1e3)).rank())
        top = x.pnl90 >= x.pnl90.quantile(0.9); bot = x.pnl90 <= x.pnl90.quantile(0.1)
        top200 = x.nlargest(NPOOL, "pnl90")
        rs.append(dict(m=m.strftime("%Y-%m"), n=len(x), rank_corr=rc, roi_corr=rr,
                       top10_pos=(x.fut[top] > 0).mean(), rest_pos=(x.fut[~top] > 0).mean(),
                       bot10_pos=(x.fut[bot] > 0).mean(),
                       top200_fut_med=top200.fut.median(), top200_pos=(top200.fut > 0).mean()))
    R = pd.DataFrame(rs)
    if R.empty:
        print("мало данных"); raise SystemExit
    pd.set_option("display.width", 200)
    print(R.round(3).to_string(index=False))
    print(f"\nсреднее по месяцам: корреляция рангов PnL {R.rank_corr.mean():+.3f} (t {R.rank_corr.mean()/R.rank_corr.std()*np.sqrt(len(R)):+.1f}), "
          f"доходности к счёту {R.roi_corr.mean():+.3f}; в плюсе в следующем месяце: верхний дециль {R.top10_pos.mean():.0%}, "
          f"остальные {R.rest_pos.mean():.0%}, нижний дециль {R.bot10_pos.mean():.0%}; топ-100 {R.top200_pos.mean():.0%}")
    # пулы
    # плацебо — постоянные 300 случайных счетов из допущенных хотя бы в 3 месяцах (без отбора по доходу); в каждом месяце —
    # те из них, кто допущен в этом месяце
    cnt = E.groupby("a").m.nunique()
    rand_set = set(random.Random(3).sample(sorted(cnt[cnt >= 3].index), min(300, int((cnt >= 3).sum()))))
    pools = {}
    for m, x in E.groupby("m"):
        pos = x[x.pnl90 > 0]
        pools[m] = dict(top=pos.nlargest(NPOOL, "pnl90").a.tolist(), roi=pos.nlargest(NPOOL, "roi90").a.tolist(),
                        bottom=x.nsmallest(NPOOL, "pnl90").a.tolist(), rand=sorted(set(x.a) & rand_set))
    pickle.dump(pools, open("s27/pools.pkl", "wb"))
    # порядок выгрузки сделок: top, плацебо, roi, bottom
    order, seen = [], set()
    for name in ("top", "rand", "roi", "bottom"):
        for m in sorted(pools):
            for a in pools[m][name]:
                if a not in seen:
                    seen.add(a); order.append(a)
    open("s27/union.txt", "w").write("\n".join(order))
    n = {name: len(set().union(*[set(p[name]) for p in pools.values()])) for name in ("top", "rand", "roi", "bottom")}
    print(f"\nпулы: {len(pools)} месяцев; адресов: всего {len(order)}, по пулам {n}")
