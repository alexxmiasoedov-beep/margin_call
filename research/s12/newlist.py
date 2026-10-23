"""Шорт новых фьючерсов Binance (идеи: США №5, СНГ №2, Корея T3): вход через 1 / 2 суток после запуска, выход через
7 / 14 / 30 суток; стоп +60% (по 15-мин максимумам); фандинг и комиссия 0,1%; хедж BTC. Признаки: рост за первые сутки,
цена на входе выше VWAP первых суток, ранний займ в маржинальном канале (посты за первые 72 ч), был ли токен в марже
до запуска фьючерса (старый токен), месяц. Только крипто (TradFi — акции, фонды, металлы — исключены)."""
import pickle, re, datetime
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb")); FU = pickle.load(open("s2/fund2y.pkl", "rb"))
kind = pickle.load(open("s12/perp_kind.pkl", "rb"))
TF = kind["tradfi"] | {"BZ", "CL", "COPPER", "NATGAS", "XAG", "XPD", "XPT", "XAU", "GIGADEV", "POPMART", "QNTX", "SPCX", "USDBRL"}
m = pickle.load(open("s7/margin.pkl", "rb")); G = m["G"]
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
ch = {}
for c, arr in G.items(): ch.setdefault(strip(c), []).append(np.unique(arr[:, 0]))
ch = {k: np.unique(np.concatenate(v)) for k, v in ch.items()}
UTC = datetime.timezone.utc
T_START = datetime.datetime(2024, 10, 5, tzinfo=UTC).timestamp(); T_END = datetime.datetime(2026, 10, 18, tzinfo=UTC).timestamp()
CH0 = datetime.datetime(2025, 2, 21, tzinfo=UTC).timestamp()
btc = K["BTC"]
def fsum(s, a, b):
    f = FU.get(s)
    return 0.0 if f is None else float(f[(f[:, 0] > a) & (f[:, 0] <= b), 2].sum())
def px(a, t):
    j = int(np.searchsorted(a["t"], int(t // 900 * 900))); j = min(j, len(a["t"]) - 1); return float(a["o"][j]), j
rows = []
for s, a in K.items():
    T0 = int(a["t"][0])
    if T0 <= T_START or s in TF or s in ("BTC", "ETH") or s.endswith("USDC"): continue
    o = a["o"].astype(float); h = a["h"].astype(float); qv = a["qv"].astype(float); c = a["c"].astype(float)
    n = len(o)
    if n < 96 * 3: continue
    vwap1 = float((qv[:96] / np.maximum((o[:96] + c[:96]) / 2, 1e-12)).sum())
    vwap1 = qv[:96].sum() / vwap1 if vwap1 > 0 else np.nan            # объём в $ / объём в монетах = средняя цена первых суток
    tt = ch.get(strip(s))
    early = int(((tt >= T0) & (tt < T0 + 72 * 3600)).sum()) if tt is not None else 0
    before = int((tt < T0 - 86400).sum()) if tt is not None else 0
    for ent_h in (24, 48):
        te = T0 + ent_h * 3600
        if te + 7 * 86400 > T_END: continue
        e, je = px(a, te)
        r_first = e / o[0] - 1
        for hold_d in (7, 14, 30):
            tx = te + hold_d * 86400
            if tx > T_END: continue
            x, jx = px(a, tx)
            hi = h[je:jx].max() / e - 1 if jx > je else 0.0
            stopped = hi >= 0.6
            ret = x / e - 1
            sp = (-0.6 - 0.005 if stopped else -ret) + fsum(s, te, tx) - 0.001
            be, _ = px(btc, te); bx, _ = px(btc, tx)
            rows.append(dict(s=s, T0=T0, ent=ent_h, hold=hold_d, sp=sp, btc=bx / be - 1 - fsum("BTC", te, tx) - 0.001,
                             fund=fsum(s, te, tx), r_first=r_first, above_vwap=e > vwap1, early=early, before=before,
                             stopped=stopped, vol1=qv[:96].sum(), ch_era=T0 >= CH0))
E = pd.DataFrame(rows); E["h"] = E.sp + E.btc
E.to_pickle("s12/newlist.pkl")
CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp()
def st(nm, g, col="sp"):
    v = g[col]; hh = g["T0"] < CUT; top = v.nlargest(5).index
    print(f"   {nm:52s} n={len(g):4d} {v.mean()*100:+6.2f}% (медиана {v.median()*100:+6.2f}%, в плюсе {(v > 0).mean():.0%}; "
          f"1-я {v[hh].mean()*100:+6.2f} / 2-я {v[~hh].mean()*100:+6.2f}; без 5 лучших {v.drop(top).mean()*100:+6.2f}; стопов {g.stopped.mean():.0%})")
print(f"новых крипто-фьючерсов: {E.s.nunique()}")
for ent in (24, 48):
    for hold in (7, 14, 30):
        g = E[(E.ent == ent) & (E.hold == hold)]
        print(f"\nвход через {ent} ч, держать {hold} сут — шорт с фандингом и комиссией (h — с хеджем BTC):")
        st("все", g); st("все, с хеджем BTC", g, "h")
        if ent == 48:
            st("цена на входе выше VWAP первых суток", g[g.above_vwap]); st("ниже VWAP", g[~g.above_vwap])
        st("за первые сутки рост > 0", g[g.r_first > 0]); st("за первые сутки падение", g[g.r_first <= 0])
        ge = g[g.ch_era]
        st("эпоха канала: ранний займ (≥ 20 постов за 72 ч)", ge[ge.early >= 20]); st("эпоха канала: займа нет", ge[ge.early == 0])
        st("токен был в марже до фьючерса (старый)", ge[ge.before > 0]); st("токена в марже не было", ge[ge.before == 0])
g = E[(E.ent == 24) & (E.hold == 14)]
print("\nпо кварталам (вход 24 ч, 14 сут), средний шорт % / событий:",
      " ".join(f"{q}: {v*100:+.1f} ({n})" for q, v, n in zip(*[(lambda gq: (gq.mean().index, gq.mean().values, gq.size().values))(g.groupby(pd.to_datetime(g.T0, unit='s').dt.to_period('Q').astype(str)).sp)][0])))
