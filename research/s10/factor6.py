"""Где живёт информация канала: среди буйных (волатильных) и выросших монет. Пары внутри терцили волатильности:
лонг монет вне канала / шорт монет канала. Разделение «вне канала» на монеты, бывшие в канале за 90 дней (маржа есть,
займов нет) и не бывшие (скорее всего, маржи нет вовсе). Комиссия 0,1% за круг на ногу, фандинг включён."""
import pickle, re, datetime
import numpy as np, pandas as pd
F = pd.read_pickle("s10/factor5b.pkl")
m = pickle.load(open("s7/margin.pkl", "rb")); G = m["G"]
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
ch = {}
for c, arr in G.items(): ch.setdefault(strip(c), []).append(arr[:, 0])
ch = {k: np.sort(np.concatenate(v)) for k, v in ch.items()}
def seen(s, W, days):
    tt = ch.get(strip(s))
    return tt is not None and (np.searchsorted(tt, W) - np.searchsorted(tt, W - days * 86400)) > 0
F["seen90"] = [seen(s, W, 90) for s, W in zip(F.s, F.W)]
UTC = datetime.timezone.utc; CUT = datetime.datetime(2025, 12, 1, tzinfo=UTC).timestamp()
F["lp"] = F.y - 0.001; F["sp"] = -F.y - 0.001
def stats(nm, w):
    w = w.dropna(); eq = w.cumsum(); dd = (eq - eq.cummax()).min(); h = w.index < CUT
    qs = w.groupby(pd.to_datetime(w.index, unit="s").to_period("Q")).sum()
    print(f"{nm:70s} {w.mean()*100:+.2f}%/нед (t {w.mean()/w.std()*np.sqrt(len(w)):.2f}, в плюсе {(w>0).mean():.0%}, 1-я/2-я {w[h].mean()*100:+.2f}/{w[~h].mean()*100:+.2f}, просадка {dd*100:.1f}%, кв. {(qs>0).sum()}/{len(qs)})")
    return w
out = F.sh == 0
F["grp"] = np.where(~out, "в канале", np.where(F.seen90, "вне: маржа есть", "вне: не было 90 дн"))
print("Средний доход лонга за неделю с фандингом (без комиссии), % / медиана / монет в неделю:")
for t in ["тихие", "средние", "буйные"]:
    g = F[F.volt == t]
    print(f"  {t:8s} " + "  ".join(f"{k}: {g[g.grp == k].y.mean()*100:+.2f} / {g[g.grp == k].y.median()*100:+.2f} ({(g.grp == k).sum()/F.W.nunique():.0f})" for k in ["вне: не было 90 дн", "вне: маржа есть", "в канале"]))
for vmin in (3e6, 10e6):
    g = F[(F.v >= vmin)].copy()
    g["volt2"] = g.groupby("W").vol.transform(lambda x: pd.qcut(x.rank(method="first"), 3, labels=False))
    b = g[g.volt2 == 2]
    print(f"\n=== объём ≥ {vmin/1e6:.0f} млн $, буйная треть")
    L = b[b.sh == 0].groupby("W").lp.mean(); S = b[b.sh > 0].groupby("W").sp.mean()
    stats("лонг буйных вне канала", L); stats("шорт буйных из канала", S); stats("пара (поровну)", (L + S) / 2)
    L2 = b[(b.sh == 0) & b.seen90].groupby("W").lp.mean(); L3 = b[(b.sh == 0) & ~b.seen90].groupby("W").lp.mean()
    stats("   лонг буйных вне канала, но с маржой (были за 90 дн)", L2); stats("   лонг буйных, не бывших в канале 90 дн", L3)
    ok = ~(b.f0 < -0.001)
    S2 = b[(b.sh > 0) & ok].groupby("W").sp.mean()
    stats("шорт буйных из канала без дорогого фандинга", S2); stats("пара с этим шортом", (L + S2) / 2)
    r = g[g.r7t == "росли"]
    L = r[r.sh == 0].groupby("W").lp.mean(); S = r[r.sh > 0].groupby("W").sp.mean()
    stats("выросшие за неделю: пара лонг вне канала / шорт из канала", (L + S) / 2)
    mk = g.groupby("W").lp.mean(); stats("для сравнения: лонг всего рынка поровну", mk)
    stats("для сравнения: лонг всех буйных", b.groupby("W").lp.mean())
