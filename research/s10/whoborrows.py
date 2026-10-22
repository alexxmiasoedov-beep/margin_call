"""Кто занимает: события MarginData × позиционирование на фьючерсах (OI, LSR топ-трейдеров по позициям и счетам, тейкеры),
займ (z-оценки, интенсивность), ончейн-приток. Механизмы:
  арбитраж/хедж — займ (продают спот) при росте OI и топ-трейдерах в лонг на фьючерсе и отрицательном фандинге;
  направленный шорт — займ при падении LSR топ-трейдеров (шортят и на фьючерсе);
  поглощение (исключение автора) — займ растёт, цена стоит, тейкеры покупают → лонг."""
import numpy as np, pandas as pd
E = pd.read_pickle("s9/md_events.pkl"); M = pd.read_pickle("s10/ev_margin.pkl"); X = pd.read_pickle("s10/ev_metrics.pkl")
D = E.merge(M, on=["s", "t"], how="left").merge(X, on=["s", "t"], how="left")
for c in ("bdz", "chng", "cex_3d"):
    if c not in D: D[c] = np.nan
D.to_pickle("s10/ev_all.pkl")
def dedup(g, h=24):
    g = g.sort_values("t"); keep = []; last = {}
    for i, s, t in zip(g.index, g.s, g.t):
        if t - last.get(s, -1e18) >= h * 3600: keep.append(i); last[s] = t
    return g.loc[keep]
OUT = ["S_10_25", "S_7_20", "L_10_10", "L_20_10", "L_30_15"]
def show(nm, g):
    g = dedup(g)
    if len(g) < 40: print(f"   {nm:62s} n={len(g)}"); return
    h1, h2 = g[g.half == 1], g[g.half == 2]
    print(f"   {nm:62s} n={len(g):5d} " + " ".join(f"{c} {g[c].mean()*100:+.2f}" for c in OUT)
          + f" | S10_25 {h1.S_10_25.mean()*100:+.2f}/{h2.S_10_25.mean()*100:+.2f} L20_10 {h1.L_20_10.mean()*100:+.2f}/{h2.L_20_10.mean()*100:+.2f}")
print("покрытие метрик:", D.groupby("ev")[["oi_ch4h", "top_pos_ch4h", "taker_1h"]].apply(lambda x: x.notna().mean()).round(2).to_dict("index"))
for ev in ("ENTER", "JUMP", "REPAY"):
    g0 = D[(D.ev == ev) & D.oi_ch4h.notna()]; print(f"\n=== {ev} (с метриками)")
    show("все", g0)
    q = g0.top_pos_ch4h.quantile([1/3, 2/3]).values
    show("LSR топ по позициям за 4 ч падает (нижняя треть)", g0[g0.top_pos_ch4h <= q[0]])
    show("LSR топ по позициям за 4 ч растёт (верхняя треть)", g0[g0.top_pos_ch4h >= q[1]])
    q = g0.oi_ch4h.quantile([1/3, 2/3]).values
    show("OI за 4 ч падает (нижняя треть)", g0[g0.oi_ch4h <= q[0]])
    show("OI за 4 ч растёт (верхняя треть)", g0[g0.oi_ch4h >= q[1]])
    show("хедж: OI ↑, топ в лонг ↑, фандинг < 0", g0[(g0.oi_ch4h >= q[1]) & (g0.top_pos_ch4h > 0) & (g0.c_f_last < 0)])
    show("направленный: OI ↑, топ ↓ (шортят и фьючерс)", g0[(g0.oi_ch4h >= q[1]) & (g0.top_pos_ch4h < 0)])
    show("закрытие шортов: OI ↓, топ ↑", g0[(g0.oi_ch4h <= q[0]) & (g0.top_pos_ch4h > 0)])
    show("поглощение: флэт 24 ч ≤ 8%, тейкеры 1 ч ≥ 55%", g0[(g0.c_rng24 <= 0.08) & (g0.taker_1h >= 1.2)])
    show("толпа в шорт: LSR всех счетов ≤ 0,8", g0[g0.all_acc <= 0.8])
    show("толпа в лонг: LSR всех счетов ≥ 2,5", g0[g0.all_acc >= 2.5])
    show("топ в шорт по позициям ≤ 0,8", g0[g0.top_pos <= 0.8])
    show("топ в лонг по позициям ≥ 2", g0[g0.top_pos >= 2])
