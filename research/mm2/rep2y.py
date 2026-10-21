"""Отчёт по бэктесту за два года: группы, варианты, по месяцам, просадка, одновременные позиции (маржа 1 USDT × 10)."""
import pickle, datetime
import numpy as np
MSK = datetime.timezone(datetime.timedelta(hours=3))
R = pickle.load(open("mm2/bt2y.pkl", "rb"))
ym = lambda t: datetime.datetime.fromtimestamp(t, MSK).strftime("%Y-%m")
MON = sorted({ym(r["t_in"]) for r in R})
def stat(name, rows, col="pnl_10", outcol="out_10", show_months=False):
    rows = [r for r in rows if r.get(col) is not None]
    if not rows: print(f"{name:44s} нет сделок"); return
    rows.sort(key=lambda r: r["t_in"]); p = np.array([r[col] for r in rows]) * 10
    eq = np.cumsum(p); dd = (eq - np.maximum.accumulate(eq)).min()
    by = {m: [x for x, r in zip(p, rows) if ym(r["t_in"]) == m] for m in MON}
    pos = sum(1 for m in MON if by[m] and sum(by[m]) > 0); act = sum(1 for m in MON if by[m])
    q = {}
    for r, x in zip(rows, p):
        d = datetime.datetime.fromtimestamp(r["t_in"], MSK); key = f"{d.year}-Q{(d.month - 1) // 3 + 1}"; q.setdefault(key, []).append(x)
    print(f"{name:44s} {len(p):5d} сд. | {p.mean() / 10:+.2%} на сделку | плюс {np.mean(p > 0):.0%} | {p.sum():+7.1f} USDT | просадка {dd:+.1f} | месяцев в плюсе {pos}/{act}")
    if show_months:
        ev = sorted([(r["t_in"], 1) for r in rows] + [(r[outcol], -1) for r in rows]); cur = mx = 0
        for _, d in ev: cur += d; mx = max(mx, cur)
        print(f"   одновременно до {mx} позиций; фандинг в среднем {np.mean([r.get('fund_10', 0) for r in rows]):+.2%} на сделку")
        print("   кварталы: " + " | ".join(f"{k}: {len(v)} сд. {sum(v):+.1f}" for k, v in sorted(q.items())))
        for m in MON:
            v = by[m]
            if v: print(f"   {m}: {len(v):3d} сделок, {sum(v):+6.1f} USDT, в среднем {np.mean(v) / 10:+.2%}, в плюсе {np.mean(np.array(v) > 0):.0%}")
K = [r for r in R if r["korea"]]
print(f"Пампов за 19.10.2024–18.10.2026: {len(R)} у {len({r['s'] for r in R})} монет; монета торговалась в Корее: {len(K)}\n")
print("=== Основное правило: доля Кореи ≥ 20% в момент пампа, тейк 10% / стоп 25% / 48 ч")
stat("корейский шорт", [r for r in K if r["share"] >= 0.2], show_months=True)
print("\n=== Сравнение (тот же выход 10/25/48 ч)")
stat("все пампы", R)
stat("монеты нет в Корее", [r for r in R if not r["korea"]])
stat("в Корее, доля < 5%", [r for r in K if r["share"] < 0.05])
stat("в Корее, доля 5–20%", [r for r in K if 0.05 <= r["share"] < 0.2])
stat("в Корее, доля ≥ 20%", [r for r in K if r["share"] >= 0.2])
print("\n=== Варианты")
stat("доля ≥ 15%", [r for r in K if r["share"] >= 0.15])
stat("доля ≥ 30%", [r for r in K if r["share"] >= 0.3])
stat("доля ≥ 20%, тейк 15% / стоп 25%", [r for r in K if r["share"] >= 0.2], "pnl_15", "out_15")
stat("доля ≥ 20% в течение 24 ч после пампа", [r for r in K if r.get("m24") is not None], "pnl24_10")
for ex in ("upbit+bithumb", "bithumb", "upbit"):
    stat(f"доля ≥ 20%, биржи: {ex}", [r for r in K if r["share"] >= 0.2 and r["ex"] == ex])
