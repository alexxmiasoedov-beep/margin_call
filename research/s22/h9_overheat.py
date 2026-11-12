"""Г9. «Перегрев займа» по правилам KRX (이우백: режим «перегрева шорта» — стоимость шорта ≥ 5× к средней за 40 дней;
тип 3 на KOSDAQ: +6,11% до назначения и −1,05% за 20 дней после, p = 0,011). Займ BOR по суткам — среднее по постам
MarginData за сутки (только дни, когда монета в канале); событие — BOR за сутки ≥ 5× средней за прошлые 40 суток
(не меньше 10 дней в канале за эти 40 суток), одно на монету за 20 суток; вход в 00:00 UTC следующих суток.
  тип 3 — цена за сутки упала меньше чем на 5% (или выросла), а за 20 суток выросла → шорт на 10 и 20 суток;
  тип 2 — цена за сутки ≤ −10% → обе стороны, вход с задержкой 0/2/5/10 суток.
Исход — доход шорта к рынку, минус средний исход той же монеты по всем её дням в канале (плацебо), с фандингом; сделки со
стопом 50%. t — с кластеризацией по дню. Сравнение — ячейка s21 «займ ×1,5 за 4 ч». Запуск из папки с данными."""
import sys
import numpy as np, pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common22 import DAY, G, GR, H, STABLE, ct, fut_of, fwd, summ, thin
from borrow_trades import sims

if __name__ == "__main__":
    g, C = GR["grid"], GR["C"]
    ev, base = [], []
    for coin, a in G.items():
        if coin in STABLE:
            continue
        s, _ = fut_of(coin)
        if s is None:
            continue
        d = (a[:, 0] // DAY).astype(int)
        day = pd.Series(a[:, 1]).groupby(d).mean()
        days, vals = day.index.values, day.values
        last = -10 ** 9
        for i, (dd, v) in enumerate(zip(days, vals)):
            T = int((dd + 1) * DAY); k = int(np.searchsorted(g, T))
            if k >= len(g) or g[k] != T or k < 20 * 24:
                continue
            row = C[GR["row"][s]]
            r1 = row[k] / row[k - 24] - 1; r20 = row[k] / row[k - 20 * 24] - 1
            base.append(dict(s=s, T=T))
            w = (days >= dd - 40) & (days < dd)
            if w.sum() < 10:
                continue
            avg = vals[w].mean()
            if avg > 0 and v >= 5 * avg and dd - last >= 20:
                ev.append(dict(s=s, T=T, ratio=v / avg, r1=r1, r20=r20)); last = dd
    E = pd.DataFrame(ev); B = thin(pd.DataFrame(base))
    print(f"событий «перегрева займа»: {len(E)}; тип 3: {((E.r1 > -0.05) & (E.r20 > 0)).sum()}, тип 2: {(E.r1 <= -0.10).sum()}; "
          f"база (дни монет в канале, одно в сутки): {len(B)}")
    hs = (24, 72, 168, 240, 480)
    cm = {h: pd.Series([fwd(s, T, h) for s, T in zip(B.s, B["T"])]).groupby(B.s.values).mean() for h in hs}
    print("база, шорт к рынку: " + " | ".join(f"{h // 24} сут {np.nanmean(cm[h]) * 100:+.2f}%" for h in hs))
    for nm, m in (("все события", E.r1 == E.r1), ("тип 3: сутки > −5%, 20 сут > 0", (E.r1 > -0.05) & (E.r20 > 0)),
                  ("тип 2: сутки ≤ −10%", E.r1 <= -0.10)):
        d = E[m]
        print(f"\n{nm}: {len(d)}")
        for h in hs:
            x = np.array([fwd(s, T, h) for s, T in zip(d.s, d["T"])]); xc = x - cm[h].reindex(d.s.values).values
            xn = np.array([fwd(s, T, h, net=True) for s, T in zip(d.s, d["T"])])
            print(f"  {h // 24:2d} сут: шорт к рынку {summ(x, d['T'].values)} | минус та же монета {np.nanmean(xc) * 100:+.2f}% "
                  f"(t {ct(xc, d['T'].values)[1]:+.1f}) | цена+фандинг {np.nanmean(xn) * 100:+.2f}%")
        for hold in (240, 480):
            R = sims(d, sl=0.5, hold_h=hold)
            if len(R):
                print(f"  сделки {hold // 24} сут, стоп 50%: {summ(R.net.values, R['T'].values)}")
        if "тип 2" in nm:
            for dl in (2, 5, 10):
                x = np.array([fwd(s, T, 240, delay=dl * 24) for s, T in zip(d.s, d["T"])])
                print(f"  вход через {dl} сут, шорт 10 сут к рынку: {summ(x, d['T'].values)}")
    E.to_pickle("s22/h9_events.pkl")
