"""Устойчивость фактора займа на ежедневной панели: 7 вариантов дня входа, затухание по горизонтам,
сетка параметров — выбор на 1-й половине (до 01.12.2025), проверка на 2-й."""
import datetime, itertools
import numpy as np, pandas as pd
D = pd.read_pickle("s10/daily_panel.pkl")
UTC = datetime.timezone.utc; CUT = datetime.datetime(2025, 12, 1, tzinfo=UTC).timestamp()
D["wd"] = pd.to_datetime(D["T"], unit="s").dt.weekday
def series(d, look=7, N=10, vmin=10e6, fcut=-0.001, hedge="market", h=7):
    d = d[(d.v >= vmin) & d[f"ret{h}"].notna()]
    y = d[f"ret{h}"] - d[f"fr{h}"]
    d = d.assign(y=y)
    pool = d[(d[f"sh{look}"] > 0)]
    if fcut is not None: pool = pool[~(pool.f0 < fcut)]
    top = pool.assign(rr=pool.groupby("T")[f"sh{look}"].rank(ascending=False, method="first")).query("rr <= @N")
    S = -top.groupby("T").y.mean() - 0.001
    if hedge == "market": L = d.groupby("T").y.mean() - 0.001; return (S + L.reindex(S.index)) / 2
    if hedge == "margin": L = d[d.seen90].groupby("T").y.mean() - 0.001; return (S + L.reindex(S.index)) / 2
    return S
def st(w):
    w = w.dropna(); h = w.index < CUT; eq = w.cumsum()
    return dict(m=w.mean(), t=w.mean() / w.std() * np.sqrt(len(w)), m1=w[h].mean(), m2=w[~h].mean(),
                t1=w[h].mean() / w[h].std() * np.sqrt(h.sum()), t2=w[~h].mean() / w[~h].std() * np.sqrt((~h).sum()), dd=(eq - eq.cummax()).min(), n=len(w))
fmt = lambda r: f"{r['m']*100:+.2f}%/нед (t {r['t']:.2f}; 1-я {r['m1']*100:+.2f} t {r['t1']:.2f} / 2-я {r['m2']*100:+.2f} t {r['t2']:.2f}; просадка {r['dd']*100:.1f}%; недель {r['n']})"
print("1) Базовый вариант (окно 7 дн, топ-10, объём ≥ 10 млн, без фандинга < −0,1%, лонг рынка) — по дням недели входа:")
names = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
allw = []
for wd in range(7):
    w = series(D[D.wd == wd]); allw.append(w); print(f"   {names[wd]}: {fmt(st(w))}")
print("   только шорт, по дням:", "  ".join(f"{names[wd]} {st(series(D[D.wd == wd], hedge=None))['m']*100:+.2f}" for wd in range(7)))
avg = pd.concat(allw).groupby(level=0).mean()
print("\n2) Затухание: средний доход за ДЕНЬ удержания, % (базовый вариант, все дни входа, перекрывающиеся окна):")
for h in (1, 3, 7, 14):
    w = series(D, h=h); print(f"   горизонт {h:2d} дн: {w.mean()/h*100:+.3f}%/день, за весь срок {w.mean()*100:+.2f}%")
print("\n3) Сетка параметров: выбор по t на 1-й половине, проверка на 2-й (недельные ряды со входом в понедельник)")
DW = D[D.wd == 0]
res = []
for look, N, vmin, fcut, hedge in itertools.product((3, 7, 14), (5, 10, 20), (3e6, 10e6, 20e6), (None, -0.0005, -0.001, -0.002), ("market", "margin", None)):
    r = st(series(DW, look, N, vmin, fcut, hedge)); r.update(look=look, N=N, vmin=vmin, fcut=fcut, hedge=hedge); res.append(r)
R = pd.DataFrame(res)
print(f"   вариантов {len(R)}; в плюсе на 2-й половине: {(R.m2 > 0).mean():.0%}; t₂ > 2: {(R.t2 > 2).mean():.0%}; медиана дохода на 2-й {R.m2.median()*100:+.2f}%/нед")
for hedge in ("market", "margin", None):
    q = R[R.hedge.astype(str) == str(hedge)]
    b = q.sort_values("t1", ascending=False).iloc[0]
    print(f"   хедж {str(hedge):6s}: лучший по 1-й половине — окно {b.look}, топ-{b.N}, объём ≥ {b.vmin/1e6:.0f} млн, фильтр фандинга {b.fcut}: "
          f"1-я {b.m1*100:+.2f} (t {b.t1:.2f}) → 2-я {b.m2*100:+.2f} (t {b.t2:.2f}); в плюсе на 2-й {(q.m2 > 0).mean():.0%} вариантов, медиана {q.m2.median()*100:+.2f}")
R.to_pickle("s10/factor8_grid.pkl")
print("\n   Влияние каждого параметра (медиана дохода на 2-й половине по всем остальным):")
for c in ("look", "N", "vmin", "fcut", "hedge"):
    print(f"   {c:6s} " + "  ".join(f"{k}: {v*100:+.2f}" for k, v in R.groupby(R[c].astype(str)).m2.median().items()))
