"""Фактор ставки маржи: дорогой займ (пул выбран) → монета хуже рынка? С фандингом и комиссией, лесенкой (вход каждый день
на 7 суток), половины истории; связь с фактором канала (доля постов MarginData); варианты отбора для журнала 🏦;
скачки ставки как события."""
import datetime
import numpy as np, pandas as pd
P = pd.read_pickle("s11/panel2.pkl")
UTC = datetime.timezone.utc
CUT = datetime.datetime(2025, 10, 15, tzinfo=UTC).timestamp()          # середина периода со ставками (11.2024–10.2026)
CH0 = datetime.datetime(2025, 3, 10, tzinfo=UTC).timestamp()           # начало данных канала
CUTC = datetime.datetime(2025, 12, 1, tzinfo=UTC).timestamp()          # половины для периода канала (как в s10)
P["y7"] = P.ret7 - P.fr7
P["rz"] = P.rate7 / P.rate60m
P["rch"] = P.rate0 / P.rate_7ago
P["wk"] = ((P["T"] - P["T"].min()) // (7 * 86400)).astype(int)
d = P[(P.v >= 10e6) & P.ret7.notna()].copy()
def nw_t(w, lag=1):
    x = w.values - w.mean(); n = len(x); g0 = (x @ x) / n
    g = sum((1 - l / (lag + 1)) * 2 * (x[l:] @ x[:-l]) / n for l in range(1, lag + 1))
    return w.mean() / np.sqrt((g0 + g) / n)
def lad(w):
    wk = ((w.index - P["T"].min()) // (7 * 86400)).astype(int); s = w.groupby(wk).mean()
    s.index = P.groupby("wk")["T"].min().reindex(s.index).values; return s
def show(nm, w, cut=CUT):
    w = lad(w).dropna(); h = w.index < cut; eq = w.cumsum()
    print(f"   {nm:64s} {w.mean()*100:+.2f}%/нед (t {nw_t(w):.2f}; 1-я {w[h].mean()*100:+.2f} / 2-я {w[~h].mean()*100:+.2f}; "
          f"просадка {(eq - eq.cummax()).min()*100:.1f}%; недель {len(w)})")
    return w
def short_top(x, key, N=10, asc=False, fcut=-0.001):
    x = x[x[key].notna()]
    if fcut is not None: x = x[~(x.f0 < fcut)]
    t = x.assign(rr=x.groupby("T")[key].rank(ascending=asc, method="first")).query("rr <= @N")
    return -t.groupby("T").y7.mean() - 0.001, t
mk = d.groupby("T").y7.mean() - 0.001
dr = d[d.rate7.notna()]
print(f"строк с объёмом ≥ 10 млн и ставкой: {len(dr)} из {len(d)} ({len(dr)/len(d):.0%}); монет в день с ставкой — медиана {dr.groupby('T').size().median():.0f}")
print("\n# A. Квинтили по ставке (каждый день, лесенка; доход лонга с фандингом, без комиссии), 11.2024–10.2026")
for key, nm in (("rate7", "ставка, средняя за 7 суток"), ("rz", "ставка за 7 суток к медиане 60 суток"), ("rate0", "ставка сейчас"), ("rch", "рост ставки за 7 суток")):
    x = dr[dr[key].notna() & np.isfinite(dr[key])].copy()
    x["q"] = x.groupby("T")[key].transform(lambda v: pd.qcut(v.rank(method="first"), 5, labels=False) if len(v) >= 25 else np.nan)
    q = x.dropna(subset=["q"]).groupby(["T", "q"]).y7.mean().unstack()
    sp = lad(q[0] - q[4]).dropna(); h = sp.index < CUT
    print(f"   {nm:42s} " + " ".join(f"Q{i+1} {lad(q[i]).mean()*100:+.2f}" for i in range(5))
          + f" | Q1−Q5 {sp.mean()*100:+.2f}%/нед (t {nw_t(sp):.2f}; 1-я {sp[h].mean()*100:+.2f} / 2-я {sp[~h].mean()*100:+.2f})")
print("\n# B. Шорт 10 монет с самой дорогой ставкой (без фандинга дешевле −0,1%/8 ч), лесенка, комиссия 0,1%")
for key, nm in (("rate7", "ставка за 7 суток"), ("rz", "ставка к медиане 60 суток"), ("rate0", "ставка сейчас")):
    S, _ = short_top(dr, key)
    show(f"{nm}: шорт", S); show(f"{nm}: шорт + лонг рынка", (S + mk.reindex(S.index)) / 2)
print("\n# C. Ставка и канал (с 10.03.2025): пересекаются ли сигналы")
c = d[(d["T"] >= CH0)].copy(); cr = c[c.rate7.notna()].copy()
rho = cr.groupby("T").apply(lambda g: g.sh7.rank().corr(g.rate7.rank()), include_groups=False)
print(f"   ранговая корреляция доли постов и ставки внутри дня: {rho.mean():+.2f}")
inn = cr[cr.sh7 > 0].copy()
inn["q"] = inn.groupby("T").rate7.transform(lambda v: pd.qcut(v.rank(method="first"), 3, labels=False) if len(v) >= 9 else np.nan)
inn["qs"] = inn.groupby("T").sh7.transform(lambda v: pd.qcut(v.rank(method="first"), 3, labels=False) if len(v) >= 9 else np.nan)
tab = inn.dropna(subset=["q", "qs"]).groupby(["qs", "q"]).y7.mean().unstack() * 100
print("   монеты канала, доход лонга за 7 суток, %: строки — доля постов (реже→чаще), столбцы — ставка (дешёвая→дорогая)")
for i in tab.index: print("     " + "  ".join(f"{tab.loc[i, j]:+.2f}" for j in tab.columns))
cut_c = lambda w: w
for nm, key in (("доля постов (как 🏦)", "sh7"), ("ставка за 7 суток", "rate7")):
    x = cr if key == "rate7" else c
    S, _ = short_top(x[x.sh7 > 0] if key == "sh7" else x, key)
    show(f"{nm}: шорт 10 + лонг рынка", (S + mk.reindex(S.index)) / 2, CUTC)
cr["sc"] = cr.groupby("T").sh7.rank(pct=True) + cr.groupby("T").rate7.rank(pct=True)
S, _ = short_top(cr, "sc"); show("доля постов + ставка (сумма рангов): шорт 10 + лонг рынка", (S + mk.reindex(S.index)) / 2, CUTC)
# регрессия Фамы–Макбета
def zr(g, cols): return (g[cols].rank(pct=True) - 0.5).fillna(0.0)
cols = ["sh7", "rate7", "vol", "r7", "f0"]; cr["lv"] = np.log(cr.v); cols.append("lv")
B = []
for T, g in cr.groupby("T"):
    if len(g) < 40: continue
    X = np.column_stack([np.ones(len(g)), zr(g, cols).values]); b = np.linalg.lstsq(X, g.y7.values, rcond=None)[0]; B.append(np.r_[T, b[1:]])
B = pd.DataFrame(B, columns=["T"] + cols).set_index("T")
print("   Фама–Макбет (доход лонга за 7 суток, разница верх−низ ранга, %; t по Ньюи–Уэсту на недельных средних):")
for c_ in cols:
    w = lad(B[c_]); h = w.index < CUTC
    print(f"     {c_:6s} {w.mean()*100:+.2f} (t {nw_t(w):.2f}; 1-я {w[h].mean()*100:+.2f} / 2-я {w[~h].mean()*100:+.2f})")
print("\n# D. Журнал 🏦: из 10 монет с наибольшей долей постов брать 5 — по волатильности (сейчас) или по ставке")
pool = cr[(cr.sh7 > 0) & ~(cr.f0 < -0.001)]
top = pool.assign(rr=pool.groupby("T").sh7.rank(ascending=False, method="first")).query("rr <= 10")
btc = P[P.s == "BTC"].set_index("T").y7
for nm, key in (("волатильность", "vol"), ("ставка за 7 суток", "rate7"), ("ставка к медиане 60 суток", "rz"), ("волатильность + ставка", "vr")):
    tp = top.copy()
    if key == "vr": tp["vr"] = tp.groupby("T").vol.rank(pct=True) + tp.groupby("T").rate7.rank(pct=True)
    tp = tp[tp[key].notna()]
    tp = tp.assign(k=tp.groupby("T")[key].rank(ascending=False, method="first")).query("k <= 5").sort_values("T")
    open_until = {}; tr = []
    for T, g in tp.groupby("T"):
        for s, y in zip(g.s, g.y7):
            if open_until.get(s, 0) > T: continue
            open_until[s] = T + 7 * 86400
            tr.append(dict(T=T, s=s, p=-y - 0.001, h=-y - 0.001 + btc.get(T, np.nan) - 0.001))
    tr = pd.DataFrame(tr); hh = tr["T"] < CUTC
    W = tr.groupby(pd.to_datetime(tr["T"], unit="s").dt.to_period("W"))[["p", "h"]].sum(); eq = W.h.cumsum()
    print(f"   {nm:28s} сделок {len(tr)}: шорт {tr.p.mean()*100:+.2f}% на сделку (1-я {tr[hh].p.mean()*100:+.2f} / 2-я {tr[~hh].p.mean()*100:+.2f}), "
          f"итог {tr.p.sum():+.1f} USDT; с хеджем BTC {tr.h.mean()*100:+.2f}% (итог {tr.h.sum():+.1f}, просадка {(eq - eq.cummax()).min():.1f})")
print("\n# E. Скачок ставки: ставка сейчас ≥ ×2 к медиане 60 суток и ≥ 0,03%/сут; шорт на 7 суток с фандингом и комиссией")
e = dr[(dr.rate0 >= 2 * dr.rate60m) & (dr.rate0 >= 0.0003)].sort_values(["s", "T"])
e = e[(e.s != e.s.shift()) | (e["T"] - e["T"].shift() > 7 * 86400)]
base = -dr.y7 - 0.001
print(f"   все монеты-дни (объём ≥ 10 млн): шорт {base.mean()*100:+.2f}% (в плюсе {(base > 0).mean():.0%})")
for nm, x in (("все скачки", e), ("скачок, монета в канале", e[e.sh7 > 0]), ("скачок, монеты нет в канале", e[e.sh7 == 0]),
              ("скачок во флэте (цена за 7 суток ±5%)", e[e.r7.abs() <= 0.05])):
    sp = -x.y7 - 0.001; h = x["T"] < CUT
    print(f"   {nm:40s} событий {len(x):4d}: шорт {sp.mean()*100:+.2f}% (медиана {sp.median()*100:+.2f}%, в плюсе {(sp > 0).mean():.0%}; "
          f"1-я {sp[h].mean()*100:+.2f} / 2-я {sp[~h].mean()*100:+.2f})")
