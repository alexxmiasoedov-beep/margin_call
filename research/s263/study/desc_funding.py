"""s263 — фандинг TradFi-перпов (s224/fund_d.pkl через extract.py): интервалы, распределение ставок, знак по часам
начисления и дням недели, начисления на потолке, внеочередные начисления (дивидендные — «special dividend funding»,
часовой интервал перед ними). Доходов сделок не считает.

Запуск из /home/user/mc_data: python3 -I <путь>/desc_funding.py"""
import datetime
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common263 import UTC, fmt_ts, group, load_f, load_meta, us_session  # noqa: E402

T_END = int(datetime.datetime(2026, 11, 20, tzinfo=UTC).timestamp())


def main():
    F = load_f()
    meta = load_meta()
    meta = meta[meta.k_n > 0].copy()
    meta["grp"] = [group(s, u) for s, u in zip(meta.sym, meta.ut)]
    rows = []
    for r in meta.itertuples():
        f = F.get(r.sym)
        if f is None or not len(f):
            continue
        for t, iv, rate in f:
            if t >= T_END:
                continue
            rows.append((r.sym, r.grp, int(t), rate))
    D = pd.DataFrame(rows, columns=["sym", "grp", "t", "rate"]).sort_values(["sym", "t"])
    D["dt"] = D.groupby("sym").t.diff()
    D["hour"] = (D.t // 3600) % 24
    D["min"] = (D.t // 60) % 60
    D["wd"] = (D.t // 86400 + 3) % 7
    D["ses"] = us_session(D.t.values)
    D.to_pickle("/dev/shm/s263/funding_rows.pkl")
    print(f"начислений: {len(D)}, символов {D.sym.nunique()}; период {fmt_ts(D.t.min())} – {fmt_ts(D.t.max())}")
    # интервалы
    D["iv_h"] = (D.dt / 3600).round(2)
    print("\nИнтервал между начислениями (часы) по группам, доля начислений:")
    for g, x in D.groupby("grp"):
        vc = x.iv_h.value_counts(normalize=True).head(6)
        print(f"  {g:9s} " + ", ".join(f"{k:g} ч {v:.0%}" for k, v in vc.items()))
    # распределение ставок
    print("\nСтавки за начисление (%): доля нулевых, медиана, среднее, 5/95 перцентили, доля |ставка| ≥ 0,1%:")
    for g, x in D.groupby("grp"):
        r = x.rate * 100
        print(f"  {g:9s} n={len(r):6d} нулевых {(r == 0).mean():.0%} медиана {r.median():+.4f} среднее {r.mean():+.4f} "
              f"p5 {r.quantile(.05):+.4f} p95 {r.quantile(.95):+.4f} |r|≥0,1% {(r.abs() >= 0.1).mean():.1%}")
    # на крипте для сравнения: BTC
    fb = F.get("BTC")
    if fb is not None:
        r = fb[:, 2] * 100
        print(f"  BTC       n={len(r):6d} нулевых {(r == 0).mean():.0%} медиана {np.median(r):+.4f} среднее {r.mean():+.4f}")
    # годовая стоимость лонга: сумма ставок за 30 сут, по группам (медиана по символам)
    T30 = T_END - 30 * 86400
    x = D[D.t >= T30].groupby(["grp", "sym"]).rate.sum() * 100 * 365 / 30
    print("\nСумма фандинга за последние 30 сут в пересчёте на год (лонг платит при +), медиана по символам и квартили, %:")
    for g, v in x.groupby(level=0):
        print(f"  {g:9s} символов {len(v):3d} медиана {v.median():+6.1f} q25 {v.quantile(.25):+6.1f} q75 {v.quantile(.75):+6.1f}")
    # знак по часу начисления (UTC) и по сессии США
    print("\nСредняя ставка (б. п.) по часу начисления UTC, акции США (одиночные + ETF + плечевые), начисления 8 ч:")
    us = D[D.grp.isin(["US_STOCK", "US_ETF", "US_LEV"]) & (D.iv_h == 8)]
    print("  " + "; ".join(f"{h:02d}: {v * 1e4:+.2f} (n={n})" for h, (v, n) in
                          us.groupby("hour").rate.agg(["mean", "size"]).iterrows()))
    print("\nСредняя ставка (б. п.) по дню недели начисления (пн…вс), акции США:")
    print("  " + "; ".join(f"{d}: {v * 1e4:+.2f}" for d, v in us.groupby("wd").rate.mean().items()))
    print("\nСредняя ставка (б. п.) по сессии США в момент начисления:")
    print("  " + "; ".join(f"{s}: {v * 1e4:+.2f} (n={n})" for s, (v, n) in
                          us.groupby("ses").rate.agg(["mean", "size"]).iterrows()))
    # по месяцам: средняя ставка акций США (б. п. за 8 ч) и доля положительных
    us8 = D[D.grp.isin(["US_STOCK", "US_ETF", "US_LEV"])].copy()
    us8["m"] = pd.to_datetime(us8.t, unit="s", utc=True).dt.strftime("%Y-%m")
    print("\nАкции США по месяцам: средняя ставка (б. п.), доля > 0, доля < 0:")
    for m, v in us8.groupby("m").rate:
        print(f"  {m}: {v.mean() * 1e4:+.2f}  > 0: {(v > 0).mean():.0%}  < 0: {(v < 0).mean():.0%}  n={len(v)}")
    # начисления вне сетки (не на 00/04/08/... и не на :00) и начисления с интервалом < 4 ч
    odd = D[(D.iv_h < 3.99) & (D.iv_h > 0)]
    print(f"\nНачисления с интервалом < 4 ч: {len(odd)} у {odd.sym.nunique()} символов")
    big = D[(D.rate <= -0.002)]
    print(f"Начисления ≤ −0,2%: {len(big)}; из них в 00/01 UTC: {int(big.hour.isin([0, 1]).sum())}")
    # кандидаты в дивидендные начисления: отрицательная ставка, перед ней часовые интервалы
    D["prev_iv"] = D.groupby("sym").iv_h.shift(1)
    div = D[(D.iv_h <= 1.01) & (D.rate < 0) & (D.hour.isin([0, 1]) | D.grp.isin(["KR_EQUITY", "HK_EQUITY", "CN_EQUITY"]))]
    # группируем: одно событие = символ + сутки
    div = div.assign(day=div.t // 86400)
    ev = div.loc[div.groupby(["sym", "day"]).rate.idxmin()]
    ev = ev[ev.rate <= -0.0003]
    print(f"\nВероятные дивидендные начисления (часовой интервал, ставка ≤ −0,03%, одно на символ и сутки): {len(ev)}")
    ev["m"] = pd.to_datetime(ev.t, unit="s", utc=True).dt.strftime("%Y-%m")
    print("  по месяцам: " + ", ".join(f"{m}: {n}" for m, n in ev.groupby("m").size().items()))
    for r in ev.sort_values("t").itertuples():
        print(f"  {fmt_ts(r.t)} {r.sym:10s} {r.grp:9s} ставка {r.rate * 100:+.3f}%")
    ev.to_csv("s263/dividend_funding_events.csv", index=False)


if __name__ == "__main__":
    main()
