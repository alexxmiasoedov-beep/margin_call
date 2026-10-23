"""Журнал 🏦 (топ-10 по доле постов канала за 7 сут → 5 самых волатильных, шорт 7 сут, одна сделка на монету) с фильтрами
по базису и фандингу (Китай №2, США №6): исключать «арбитражный хедж» (фандинг ≤ −0,03%/8 ч и премия ≤ −0,1%), требовать
премию ≥ 0, исключать нижнюю квинтиль фандинга. Премия — среднее premiumIndex за 3 сут до входа (15-мин свечи)."""
import pickle, datetime
import numpy as np, pandas as pd
P = pd.read_pickle("s11/panel2.pkl"); PR = pickle.load(open("s12/prem.pkl", "rb"))
UTC = datetime.timezone.utc; CH0 = datetime.datetime(2025, 3, 10, tzinfo=UTC).timestamp(); CUTC = datetime.datetime(2025, 12, 1, tzinfo=UTC).timestamp()
d = P[(P["T"] >= CH0) & (P.v >= 10e6) & P.ret7.notna()].copy(); d["y7"] = d.ret7 - d.fr7
def prem(s, T, hours):
    v = PR.get(s)
    if v is None: return np.nan
    t, p = v; a, b = np.searchsorted(t, T - hours * 3600), np.searchsorted(t, T - 900)
    return float(p[a:b + 1].mean()) if b >= a and b < len(t) else np.nan
cand = d[(d.sh7 > 0)].copy()
cand["p3"] = [prem(s, T, 72) for s, T in zip(cand.s, cand["T"])]
cand["p1"] = [prem(s, T, 24) for s, T in zip(cand.s, cand["T"])]
print("премия известна у", f"{cand.p3.notna().mean():.0%}", "кандидатов; медиана премии за 3 сут", f"{cand.p3.median()*100:+.3f}%")
btc = P[P.s == "BTC"].set_index("T").eval("ret7 - fr7")
def journal(pool, nm):
    top = pool.assign(rr=pool.groupby("T").sh7.rank(ascending=False, method="first")).query("rr <= 10")
    tp = top.assign(vr=top.groupby("T").vol.rank(ascending=False, method="first")).query("vr <= 5").sort_values("T")
    open_until = {}; tr = []
    for T, g in tp.groupby("T"):
        for s, y in zip(g.s, g.y7):
            if open_until.get(s, 0) > T: continue
            open_until[s] = T + 7 * 86400
            tr.append(dict(T=T, s=s, p=-y - 0.001, h=-y - 0.001 + btc.get(T, np.nan) - 0.001))
    tr = pd.DataFrame(tr); hh = tr["T"] < CUTC
    W = tr.groupby(pd.to_datetime(tr["T"], unit="s").dt.to_period("W")).h.sum(); eq = W.cumsum()
    print(f"   {nm:58s} сделок {len(tr):4d}: шорт {tr.p.mean()*100:+.2f}% (1-я {tr[hh].p.mean()*100:+.2f} / 2-я {tr[~hh].p.mean()*100:+.2f}; "
          f"в плюсе {(tr.p > 0).mean():.0%}) | с хеджем {tr.h.mean()*100:+.2f}%, итог {tr.h.sum():+.1f} USDT, просадка {(eq - eq.cummax()).min():.1f}")
base = cand[~(cand.f0 < -0.001)]
journal(base, "базовый 🏦 (фандинг ≥ −0,1%/8 ч)")
journal(base[~((base.f0 <= -0.0003) & (base.p3 <= -0.001))], "без «арбитражного хеджа» (фандинг ≤ −0,03% и премия ≤ −0,1%)")
journal(base[base.p3 >= 0], "только премия за 3 сут ≥ 0")
journal(base[base.p3 >= -0.0005], "премия за 3 сут ≥ −0,05%")
journal(base[base.p1 >= 0], "только премия за сутки ≥ 0")
q = base.groupby("T").f0.transform(lambda x: x.rank(pct=True))
journal(base[q > 0.2], "без нижней квинтили фандинга (относительно)")
journal(cand[~(cand.f0 < -0.0005)], "фандинг ≥ −0,05%/8 ч")
journal(cand[~(cand.f0 < -0.0003)], "фандинг ≥ −0,03%/8 ч")
journal(cand, "без фильтра фандинга")
