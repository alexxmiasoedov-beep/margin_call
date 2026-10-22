"""Ончейн-отток с кошельков Binance и займы: общий эффект оттока по рынку, взаимодействие с каналом,
шорт топ-N по займам только среди монет с оттоком. Период с ончейн-данными (в основном с 12.2025) делим на две части."""
import datetime, re
import numpy as np, pandas as pd
exec(open("s10/factor9.py").read().split("# Ончейн")[0].split("print(\"BTC")[0])
Q = pd.read_pickle("s10/cex_qty.pkl")
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
d = D[(D.v >= 10e6) & D.ret7.notna()].copy(); d["y7"] = d.ret7 - d.fr7
dates = pd.to_datetime(d["T"], unit="s").dt.normalize()
Qs = {c: Q[c] for c in Q.columns}
def dq(s, dt, back=7):
    q = Qs.get(strip(s))
    if q is None: return np.nan
    x0, x1 = q.get(dt - pd.Timedelta(days=2 + back), np.nan), q.get(dt - pd.Timedelta(days=2), np.nan)
    return x1 / x0 - 1 if np.isfinite(x0) and x0 > 0 and np.isfinite(x1) else np.nan
d["dq"] = [dq(s, t) for s, t in zip(d.s, dates)]
d["dq3"] = [dq(s, t, 3) for s, t in zip(d.s, dates)]
o = d[d.dq.notna()].copy()
MID = datetime.datetime(2026, 4, 15, tzinfo=datetime.timezone.utc).timestamp()
print(f"монет с ончейн-данными в день (объём ≥ 10 млн): медиана {o.groupby('T').size().median():.0f}; дни {datetime.datetime.utcfromtimestamp(o['T'].min()):%d.%m.%Y}–{datetime.datetime.utcfromtimestamp(o['T'].max()):%d.%m.%Y}")
o["q"] = o.groupby("T").dq.transform(lambda x: pd.qcut(x.rank(method="first"), 5, labels=False) if len(x) >= 20 else np.nan)
z = o.dropna(subset=["q"]).groupby(["T", "q"]).y7.mean().unstack()
print("Весь рынок с данными: доход ЛОНГА 7 дн по квинтилям изменения баланса Binance (Q0 — сильнейший отток), %:")
print("   " + "  ".join(f"Q{i}: {z[i].mean()*100:+.2f}" for i in range(5)), f"| Q4−Q0 {(z[4]-z[0]).mean()*100:+.2f}")
h = z.index < MID
print("   до 15.04.2026: " + "  ".join(f"{z[i][h].mean()*100:+.2f}" for i in range(5)) + " | после: " + "  ".join(f"{z[i][~h].mean()*100:+.2f}" for i in range(5)))
o["inch"] = o.sh7 > 0
o["out5"] = o.dq < -0.05
print("\nДоход ЛОНГА 7 дн, %: (в канале да/нет) × (отток > 5% да/нет); в скобках — позиций в день")
for a in (False, True):
    for b in (False, True):
        x = o[(o.inch == a) & (o.out5 == b)]
        print(f"   канал {'да' if a else 'нет'}, отток>5% {'да' if b else 'нет'}: {x.y7.mean()*100:+.2f} (медиана {x.y7.median()*100:+.2f}) ({len(x)/o['T'].nunique():.1f})")
pool = o[(o.sh7 > 0) & ~(o.f0 < -0.001)]
mk = o.groupby("T").y7.mean()
print("\nШорт топ-N по займам среди монет с ончейн-данными (лесенка; 1-я/2-я = до/после 15.04.2026):")
def lad2(w):
    wk = ((w.index - D["T"].min()) // (7 * 86400)).astype(int); s = w.groupby(wk).mean()
    s.index = D.groupby("wk")["T"].min().reindex(s.index).values; return s
def show(nm, w):
    w = lad2(w).dropna(); hh = w.index < MID; eq = w.cumsum()
    print(f"   {nm:52s} {w.mean()*100:+.2f}%/нед (t {nw_t(w):.2f}; до/после {w[hh].mean()*100:+.2f}/{w[~hh].mean()*100:+.2f}; просадка {(eq-eq.cummax()).min()*100:.1f}%; недель {len(w)})")
for N in (5, 10):
    for nm, pp in [("все", pool), ("отток > 1%", pool[pool.dq < -0.01]), ("отток > 5%", pool[pool.dq < -0.05]), ("без оттока (≥ −1%)", pool[pool.dq >= -0.01])]:
        tt = pp.assign(rr=pp.groupby("T").sh7.rank(ascending=False, method="first")).query("rr <= @N")
        S = -tt.groupby("T").y7.mean() - 0.001
        show(f"топ-{N}, {nm}: шорт", S); show(f"топ-{N}, {nm}: шорт + лонг рынка", (S + mk.reindex(S.index) - 0.001) / 2)
print("\nТолько ончейн, без канала: шорт 10 монет с сильнейшим оттоком за 7 дн (фильтр фандинга) + лонг рынка:")
pp = o[~(o.f0 < -0.001)]
tt = pp.assign(rr=pp.groupby("T").dq.rank(ascending=True, method="first")).query("rr <= 10")
S = -tt.groupby("T").y7.mean() - 0.001; show("шорт", S); show("шорт + лонг рынка", (S + mk.reindex(S.index) - 0.001) / 2)
o.to_pickle("s10/factor10.pkl")
