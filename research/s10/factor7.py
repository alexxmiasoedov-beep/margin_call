"""Чем топ-10 по присутствию в канале отличается от остальных монет канала, и можно ли повторить результат без канала
(ценовыми аналогами: топ-10 по волатильности, объёму, росту и т. п. с тем же фильтром фандинга)."""
import datetime
import numpy as np, pandas as pd
F = pd.read_pickle("s10/factor5b.pkl")
UTC = datetime.timezone.utc; CUT = datetime.datetime(2025, 12, 1, tzinfo=UTC).timestamp()
F["lp"] = F.y - 0.001; F["sp"] = -F.y - 0.001
def stats(nm, w):
    w = w.dropna(); eq = w.cumsum(); dd = (eq - eq.cummax()).min(); h = w.index < CUT
    qs = w.groupby(pd.to_datetime(w.index, unit="s").to_period("Q")).sum()
    print(f"{nm:58s} {w.mean()*100:+.2f}%/нед (t {w.mean()/w.std()*np.sqrt(len(w)):.2f}, в плюсе {(w>0).mean():.0%}, 1-я/2-я {w[h].mean()*100:+.2f}/{w[~h].mean()*100:+.2f}, просадка {dd*100:.1f}%, кв. {(qs>0).sum()}/{len(qs)})")
    return w
g = F[F.v >= 10e6].copy(); ok = ~(g.f0 < -0.001)
inn = g[g.sh > 0].copy(); inn["r"] = inn.groupby("W").sh.rank(ascending=False, method="first")
top = inn[ok.reindex(inn.index)].sort_values(["W", "r"]).groupby("W").head(10)
rest = inn.drop(top.index)
cols = ["sh", "v", "vol", "r1", "r7", "r30", "mx", "vchg", "f0", "fr7", "tbr", "bor", "br"]
print("Медианы признаков: топ-10 канала / остальные монеты канала / монеты вне канала")
for c in cols:
    print(f"   {c:5s} {top[c].median():+.4g}  /  {rest[c].median():+.4g}  /  {g[g.sh == 0][c].median():+.4g}")
mk = g.groupby("W").lp.mean()
print("\nШорт топ-10 по признаку (без фандинга дешевле −0,1%) + лонг рынка поровну, объём ≥ 10 млн $:")
gg = g[ok]
for nm, key, asc in [("доля присутствия в канале (sh)", "sh", False), ("волатильность", "vol", False), ("объём", "v", False),
                     ("рост за 7 дней", "r7", False), ("падение за 7 дней", "r7", True), ("рост за 30 дней", "r30", False),
                     ("падение за 30 дней", "r30", True), ("фандинг сейчас (самый высокий)", "f0", False), ("фандинг за неделю", "fr7", False),
                     ("рост объёма", "vchg", False), ("доля покупок тейкеров", "tbr", False), ("макс. дневной рост", "mx", False)]:
    sel = gg.assign(rr=gg.groupby("W")[key].rank(ascending=asc, method="first")).query("rr <= 10")
    S = sel.groupby("W").sp.mean()
    stats(f"   {nm}", (S + mk.reindex(S.index)) / 2)
print("\nТо же, но шорт только среди монет С МАРЖОЙ (были в канале за 90 дней) — чистое сравнение внутри маржинальных:")
import pickle, re
m = pickle.load(open("s7/margin.pkl", "rb")); G = m["G"]
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
ch = {}
for c, arr in G.items(): ch.setdefault(strip(c), []).append(arr[:, 0])
ch = {k: np.sort(np.concatenate(v)) for k, v in ch.items()}
def seen(s, W, days):
    tt = ch.get(strip(s)); return tt is not None and (np.searchsorted(tt, W) - np.searchsorted(tt, W - days * 86400)) > 0
g["mg"] = [seen(s, W, 90) for s, W in zip(g.s, g.W)]
gm = g[ok & g.mg]
mkm = g[g.mg].groupby("W").lp.mean()
for nm, key, asc in [("доля присутствия в канале (sh)", "sh", False), ("волатильность", "vol", False), ("объём", "v", False),
                     ("рост за 7 дней", "r7", False), ("падение за 30 дней", "r30", True), ("фандинг за неделю", "fr7", False)]:
    sel = gm.assign(rr=gm.groupby("W")[key].rank(ascending=asc, method="first")).query("rr <= 10")
    S = sel.groupby("W").sp.mean()
    stats(f"   {nm} (+ лонг маржинальных)", (S + mkm.reindex(S.index)) / 2)
print(f"\nмаржинальных монет в неделю (объём ≥ 10 млн): {g.mg.sum()/g.W.nunique():.0f}, без маржи: {(~g.mg).sum()/g.W.nunique():.0f}")
stats("лонг маржинальных поровну", mkm); stats("лонг без маржи поровну", g[~g.mg].groupby("W").lp.mean())
stats("пара: лонг без маржи / шорт маржинальных", (g[~g.mg].groupby("W").lp.mean() + g[g.mg].groupby("W").sp.mean()) / 2)
