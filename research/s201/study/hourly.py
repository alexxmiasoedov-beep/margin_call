"""s201: почасовые ключи (только описание, без доходов).
A) Баланс меток owner->binance по часам: рывки ≥ 0,5% обращения за час — ступенька одним переводом или постепенный
   набор; совпадение с нашими заводами на адреса Binance (s195, тот же час ±1); «системные» часы, когда прыгают
   сразу несколько монет (перекладка внутри биржи); частота часовых событий (первое у монеты за 48 ч, как в 🐋).
B) Почасовые трендовые слова Santiment → перпы: первый час в топ-10 (первый за 14 сут), сверка с дневным
   trending_words_rank, час суток, доля в день пампа (описание дня)."""
import pickle
import re

import numpy as np
import pandas as pd

D = "/home/user/mc_data/s201"
P = pickle.load(open(f"{D}/panel.pkl", "rb"))
G = pd.read_csv(f"{D}/map.csv")
V = pd.read_csv(f"{D}/map_variants.csv")
prim = dict(zip(G.s, G.slug))
inv = {}
for s, sl in prim.items():
    inv.setdefault(sl, s)
for r in V.itertuples():
    inv.setdefault(r.slug, r.s)
DAYS = P["social_volume_total"].index
CUT = pd.Timestamp("2026-05-01", tz="UTC")
circ = P["circ"]
c = P["perp_c"]
r_cc = c / c.shift(1) - 1

# ---------- A ----------
H = pd.read_pickle(f"{D}/daily/labelled_historical_balance__binance__1h.pkl")
H = H[H.slug.isin(inv)]
H["s"] = H.slug.map(inv)
W = H.pivot_table(index="datetime", columns="s", values="value", aggfunc="last").sort_index()
hours = pd.date_range(DAYS[0], DAYS[-1] + pd.Timedelta(hours=23), freq="h", tz="UTC")
W = W.reindex(hours)
circ_h = circ.reindex(columns=W.columns).reindex(hours, method="ffill")
dh = W.diff() / circ_h
jump = dh >= 0.005
n_same = jump.sum(axis=1)
print("A) Часовые рывки баланса Binance (метки Santiment) ≥ 0,5% обращения за час:")
print(f"  всего монето-часов: {int(jump.values.sum())}; часов, где прыгнули ≥ 3 монеты сразу: {int((n_same >= 3).sum())} "
      f"(в них {int(jump[n_same >= 3].values.sum())} рывков)")
top = n_same.sort_values(ascending=False).head(5)
print("  крупнейшие «системные» часы:", ", ".join(f"{k:%Y-%m-%d %H}:00 — {v}" for k, v in top.items()))
# первое у монеты за 48 ч, без системных часов
ev = jump & (n_same < 3).values[:, None]
prev = ev.shift(1).rolling(48, min_periods=1).max().fillna(0).astype(bool)
first = ev & ~prev
first.iloc[:24 * 21] = False
st = first.stack()
st = st[st]
print(f"  первых за 48 ч рывков (без системных часов): {len(st)}")
dep = pd.read_pickle("/home/user/mc_data/s195_deposits.pkl")
dep = dep[(dep.exch == "Binance") & dep.perp.isin(W.columns)]
dep["h"] = pd.to_datetime(dep.t, unit="s", utc=True).dt.floor("h")
dep = dep[(dep.h >= hours[0]) & (dep.h <= hours[-1])]
dh_sum = dep.groupby(["perp", "h"]).frac.sum()
dh_max = dep.groupby(["perp", "h"]).frac.max()
rows = []
for (h, s) in st.index:
    win = [h + pd.Timedelta(hours=k) for k in (-1, 0)]
    mx = max(dh_max.get((s, x), 0) for x in win)
    sm = sum(dh_sum.get((s, x), 0) for x in win)
    jv = float(dh.at[h, s])
    k = ("один наш завод ≥ 0,5% (🐋)" if mx >= 0.005 else
         "наши заводы поменьше ≥ половины рывка" if sm >= 0.5 * jv else "нет в нашем сборе")
    d = h.floor("D")
    rows.append(dict(s=s, h=h, k=k, jump=jv, hour=h.hour, pump=bool(r_cc.at[d, s] >= 0.10) if s in r_cc.columns else False,
                     calm=bool(abs(r_cc.at[d - pd.Timedelta(days=1), s]) <= 0.05) if (s in r_cc.columns and d > DAYS[0]) else False))
R = pd.DataFrame(rows)
mon = lambda x: x / ((hours[-1] - hours[24 * 21]).days / 30.44)
for k, g in R.groupby("k"):
    h1 = (g.h < CUT).sum() / ((CUT - hours[24 * 21]).days / 30.44)
    h2 = (g.h >= CUT).sum() / ((hours[-1] - CUT).days / 30.44)
    print(f"  {k}: {len(g)} ({mon(len(g)):.1f}/мес; H1 {h1:.1f}, H2 {h2:.1f}); медиана рывка {g.jump.median()*100:.2f}%; "
          f"накануне спокойно (|r_cc| ≤ 5%) {g.calm.mean()*100:.0f}%; в день памп ≥ +10% {g.pump.mean()*100:.0f}%")
# ступенька или набор: доля суточного прироста, пришедшая за один час
dd = W.resample("D").last().diff()
mxh = W.diff().resample("D").max()
o4 = (dd / circ.reindex(columns=W.columns).reindex(dd.index)) >= 0.005
conc = (mxh / dd).where(o4 & (dd > 0)).stack().dropna().astype(float)
print(f"  дни O4 (+0,5% за сутки): доля суточного прироста за самый крупный час — квартили "
      f"{[round(x, 2) for x in conc.quantile([.25, .5, .75]).tolist()]}; ≥ 0,8 у {float((conc >= 0.8).mean())*100:.0f}% "
      f"(ступенька одним часом), ≤ 0,3 у {float((conc <= 0.3).mean())*100:.0f}% (постепенный набор); дней {len(conc)}")
R.to_pickle(f"{D}/binance_hourly_events.pkl")

# ---------- B ----------
T = pd.read_pickle(f"{D}/trending_hourly.pkl")
PR = {p["slug"]: p for p in __import__("json").load(open(f"{D}/projects.json"))}
STOP = {"true", "one", "ai", "act", "open", "ten", "sun", "core", "gas", "hot", "id", "key", "magic", "pump", "sign",
        "move", "zero", "big", "home", "ton", "people", "dog", "cat", "trump", "near", "flow", "mask", "ip", "ace", "bank",
        "dash", "edge", "fun", "game", "gold", "hook", "jet", "kite", "life", "light", "mind", "moon", "news", "party",
        "play", "power", "real", "safe", "space", "star", "time", "top", "uni", "virtual", "wave", "win", "x", "yes",
        "bitcoin", "btc", "eth", "ethereum", "sol", "solana", "xrp", "bnb", "doge", "usdt", "usdc", "ondo", "sui", "ada"}
word2s = {}
for s, sl in prim.items():
    base = re.sub(r"^(1000000|1000|1M)", "", s).lower()
    names = {base, sl.lower(), (PR.get(sl, {}).get("name") or "").lower()}
    for w in names:
        if w and w not in STOP and len(w) >= 3:
            word2s.setdefault(w, set()).add(s)
T["s"] = T.word.map(lambda w: next(iter(word2s[w])) if w in word2s and len(word2s[w]) == 1 else None)
M = T.dropna(subset=["s"])
print(f"\nB) Почасовые тренды: часов {T.datetime.nunique()}, слов {T.word.nunique()}; совпали с перпами (тикер, slug, имя, "
      f"без стоп-слов) {M.word.nunique()} слов, {M.s.nunique()} перпов, {len(M)} строк")
for top_n in (10, 3):
    m = M[M["rank"] <= top_n].sort_values("datetime")
    first_h = []
    last = {}
    for r in m.itertuples():
        if r.datetime - last.get(r.s, pd.Timestamp("2000-01-01", tz="UTC")) >= pd.Timedelta(days=14):
            first_h.append((r.s, r.datetime, r.word, r.rank))
        last[r.s] = r.datetime
    F = pd.DataFrame(first_h, columns=["s", "h", "word", "rank"])
    F = F[F.h >= hours[0] + pd.Timedelta(days=14)]
    F["d"] = F.h.dt.floor("D")
    F["pump"] = [bool(r_cc.at[r.d, r.s] >= 0.10) if r.s in r_cc.columns else False for r in F.itertuples()]
    F["pump_prev"] = [bool(r_cc.at[r.d - pd.Timedelta(days=1), r.s] >= 0.10) if r.s in r_cc.columns else False
                      for r in F.itertuples()]
    months = (hours[-1] - hours[0] - pd.Timedelta(days=14)).days / 30.44
    h1 = (F.h < CUT).sum() / ((CUT - hours[0] - pd.Timedelta(days=14)).days / 30.44)
    h2 = (F.h >= CUT).sum() / ((hours[-1] - CUT).days / 30.44)
    print(f"  первый час в топ-{top_n} (первый за 14 сут): {len(F)} событий, {len(F)/months:.1f}/мес (H1 {h1:.1f}, H2 {h2:.1f}); "
          f"в день памп ≥ +10% {F.pump.mean()*100:.0f}%, накануне {F.pump_prev.mean()*100:.0f}%")
    print("    час UTC (квартили):", F.h.dt.hour.quantile([.25, .5, .75]).tolist(),
          "| пример:", "; ".join(f"{r.s} {r.h:%m-%d %H}h «{r.word}»" for r in F.head(6).itertuples()))
    F.to_pickle(f"{D}/trending_first_top{top_n}.pkl")
# сверка с дневной метрикой
tw = P["trending_words_rank"]
dm = (tw <= 10).stack()
dm = dm[dm]
hit = M[M["rank"] <= 10].assign(d=lambda x: x.datetime.dt.floor("D")).groupby(["d", "s"]).size()
both = sum(1 for (d, s) in dm.index if (d, s) in hit.index)
print(f"  сверка: перпо-дней с дневным trending_words_rank ≤ 10: {len(dm)}; из них слово перпа в почасовом топ-10 в тот же день: "
      f"{both} ({both/len(dm)*100:.0f}%)")
