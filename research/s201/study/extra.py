"""s201: следующие ключи после events.py (только описание, без доходов):
1) рывки баланса Binance (O4) — чем объясняются: наш крупный завод (≥ 0,5%, как 🐋), сумма наших заводов поменьше
   (s195, переводы на адреса Binance из нашего списка меток), или ничем из нашего сбора (метки Santiment шире);
2) ончейн-события по сетям (ETH / BEP20 / прочие) — что есть вне Ethereum;
3) Telegram-всплески (S4) и переписанная история Telegram (computedAt в 10.2026);
4) тренды Santiment как в их «Peak Hype» (топ-3) и топ-10 — частоты;
5) частоты кандидатов гипотез по половинам (до и после 2026-05-01) с фильтрами без заглядывания."""
import pickle

import numpy as np
import pandas as pd

D = "/home/user/mc_data/s201"
P = pickle.load(open(f"{D}/panel.pkl", "rb"))
X = pickle.load(open(f"{D}/events.pkl", "rb"))
EV = X["EV"]
DAYS = P["social_volume_total"].index
CUT = pd.Timestamp("2026-05-01", tz="UTC")
c = P["perp_c"]
r_cc = c / c.shift(1) - 1
calm = r_cc.abs() <= 0.05
G = pd.read_csv(f"{D}/map.csv")
V = pd.read_csv(f"{D}/map_variants.csv")
infra = dict(zip(G.s, G.infrastructure.fillna("None")))


def per_month(e, base_days=None):
    days = e.index
    d0 = days[20]
    m1 = ((days >= d0) & (days < CUT)).sum() / 30.44
    m2 = (days >= CUT).sum() / 30.44
    n1 = int(e[(days >= d0) & (days < CUT)].values.sum())
    n2 = int(e[days >= CUT].values.sum())
    return n1 + n2, (n1 + n2) / (m1 + m2), n1 / m1, n2 / m2


def show(name, e):
    n, a, h1, h2 = per_month(e)
    print(f"  {name}: {n} событий, {a:.1f} в месяц (H1 {h1:.1f}, H2 {h2:.1f})")


# --- 1. рывки баланса Binance ---
dep = pd.read_pickle("/home/user/mc_data/s195_deposits.pkl")
dep = dep[dep.exch == "Binance"]
dep["d"] = pd.to_datetime(dep.t, unit="s", utc=True).dt.floor("D")
dep = dep[(dep.d >= DAYS[0]) & (dep.d <= DAYS[-1])]
agg = dep.groupby(["perp", "d"]).frac.agg(["sum", "max", "count"])
bn = P["labelled_historical_balance__binance"]
circ = P["circ"]
dbn = bn.diff() / circ.reindex(columns=bn.columns)
o4 = EV["O4 Binance +0,5%"]
st = o4.stack()
st = st[st]
cat = []
for (d, s) in st.index:
    a = agg.loc[(s, d)] if (s, d) in agg.index else None
    b = agg.loc[(s, d - pd.Timedelta(days=1))] if (s, d - pd.Timedelta(days=1)) in agg.index else None
    mx = max(a["max"] if a is not None else 0, b["max"] if b is not None else 0)
    sm = (a["sum"] if a is not None else 0)
    dv = float(dbn.at[d, s])
    if mx >= 0.005:
        k = "наш крупный завод ≥ 0,5% (как 🐋)"
    elif sm >= 0.5 * dv:
        k = "наши заводы поменьше покрывают ≥ половины рывка"
    else:
        k = "в нашем сборе почти ничего (метки Santiment шире)"
    nxt = dbn[s].shift(-1).get(d, np.nan)
    cat.append(dict(s=s, d=d, k=k, dv=dv, sm=sm, calm=bool(calm.at[d, s]) if s in calm.columns else False,
                    revert=bool(nxt <= -0.5 * dv) if nxt == nxt else False, infra=infra.get(s)))
C = pd.DataFrame(cat)
print("1) Рывки баланса Binance по меткам Santiment (O4: +0,5% обращения за сутки), всего", len(C))
for k, g in C.groupby("k"):
    print(f"  {k}: {len(g)} ({len(g)/len(C)*100:.0f}%), в спокойный день {g.calm.mean()*100:.0f}%, "
          f"на следующий день баланс вернулся (≥ половины) у {g.revert.mean()*100:.0f}% — описание, не правило")
o4u = o4.copy() * False
for r in C[(C.k != "наш крупный завод ≥ 0,5% (как 🐋)") & C.calm].itertuples():
    o4u.at[r.d, r.s] = True
show("O4 без нашего крупного завода, спокойный день (|r_cc| ≤ 5%)", o4u)
o4w = o4.copy() * False
for r in C[(C.k == "наш крупный завод ≥ 0,5% (как 🐋)") & C.calm].itertuples():
    o4w.at[r.d, r.s] = True
show("O4 с нашим крупным заводом, спокойный день", o4w)

# --- 2. ончейн-события по сетям ---
print("\n2) Ончейн-события по сетям основного slug перпа (в месяц)")
for name in ("O1 age consumed", "O1b age consumed сильный", "O2 спящие 365d", "O6 сделки китов ≥ 1 млн $",
             "O6b сделки китов ≥ 100 тыс. $", "O9 новые адреса"):
    e = EV[name]
    by = {}
    for s in e.columns:
        k = infra.get(s, "None")
        k = k if k in ("ETH", "BEP20") else "прочие"
        by.setdefault(k, []).append(s)
    parts = []
    for k, cols in sorted(by.items()):
        n, a, h1, h2 = per_month(e[cols])
        parts.append(f"{k}: {len(cols)} перпов, {a:.1f}/мес (H1 {h1:.1f}, H2 {h2:.1f})")
    print(f"  {name} — " + "; ".join(parts))
# перпы с BEP20-вариантом при ETH-основном
bep_var = sorted(set(V[V.infrastructure == "BEP20"].s))
print("  перпы, где ончейн BNB Chain есть только у варианта bnb-:", bep_var)

# --- 3. Telegram ---
tgr = pd.read_pickle(f"{D}/daily/social_volume_telegram.pkl")
tgr["d"] = tgr.datetime.dt.floor("D")
tgr["lag"] = (pd.to_datetime(tgr.computedAt, utc=True) - tgr.datetime).dt.total_seconds() / 86400
prim = dict(zip(G.s, G.slug))
lag = tgr.pivot_table(index="d", columns="slug", values="lag").reindex(DAYS)
lag = pd.DataFrame({s: lag[sl] for s, sl in prim.items() if sl in lag.columns}, index=DAYS)
s4 = EV["S4 только Telegram"]
st = s4.stack()
st = st[st]
lags = np.array([lag.at[d, s] for (d, s) in st.index if s in lag.columns])
print(f"\n3) S4 «только Telegram»: {len(lags)} событий; значение Telegram в день события пересчитано позже 40 сут "
      f"после дня у {np.mean(lags > 40)*100:.0f}% (у всех ячеек Telegram — {np.mean(lag.stack() > 40)*100:.0f}%)")
dd = pd.Series([d for (d, s) in st.index]).value_counts()
print(f"  дней с ≥ 5 событиями S4 сразу: {int((dd >= 5).sum())}; крупнейшие дни: "
      + ", ".join(f"{k.date()}:{v}" for k, v in dd.head(5).items()))
for nm in ("S1 соцобъём ×", "S3 в трендах Santiment", "S6 Twitter", "O4 Binance +0,5%", "O2 спящие 365d"):
    e = EV[nm]
    st2 = e.stack()
    st2 = st2[st2]
    dd2 = pd.Series([d for (d, s) in st2.index]).value_counts()
    print(f"  {nm}: дней с ≥ 5 событиями сразу {int((dd2 >= 5).sum())}, крупнейший день {dd2.index[0].date()}:{dd2.iloc[0]}")

# --- 4. тренды ---
tw = P["trending_words_rank"]
print("\n4) Тренды Santiment (trending_words_rank, дневной ранг; данные только для дней в списке)")
print("  распределение рангов:", tw.stack().quantile([.05, .25, .5, .75, .95]).round(0).tolist(),
      "| перпо-дней с рангом ≤ 3:", int((tw <= 3).sum().sum()), "≤ 10:", int((tw <= 10).sum().sum()))
for thr, win in ((3, 14), (10, 14), (70, 14), (70, 30)):
    cond = tw <= thr
    prev = cond.shift(1).rolling(win, min_periods=1).max().fillna(0).astype(bool)
    e = cond & ~prev & (P["perp_qv"].reindex(columns=tw.columns).fillna(0) > 0)
    e.iloc[:win] = False
    n, a, h1, h2 = per_month(e)
    pp = (r_cc.reindex(columns=tw.columns) >= 0.10).where(e).stack().mean()
    pv = (r_cc.reindex(columns=tw.columns).shift(1) >= 0.10).where(e).stack().mean()
    print(f"  ранг ≤ {thr}, первый за {win} сут: {n} событий, {a:.1f}/мес (H1 {h1:.1f}, H2 {h2:.1f}); "
          f"в день памп ≥ +10% {pp*100:.0f}%, накануне {pv*100:.0f}%")

# --- 5. кандидаты гипотез с фильтрами (частоты) ---
print("\n5) Частоты кандидатов (в месяц, H1 / H2), фильтр «спокойный день события» |r_cc| ≤ 5%")
U = pd.read_pickle("/home/user/mc_data/s142_2024–2026.pkl")[["s", "T"]]
U["d"] = pd.to_datetime(U["T"], unit="s", utc=True).dt.floor("D")
near_unlock = pd.DataFrame(False, index=DAYS, columns=circ.columns)
for r in U.itertuples():
    if r.s in near_unlock.columns:
        near_unlock.loc[r.d - pd.Timedelta(days=3): r.d + pd.Timedelta(days=3), r.s] = True
W = pd.read_pickle("/home/user/mc_data/s167lv_2024–2026.pkl")[["s", "t", "B"]]
W = W[W.B]
W["d"] = pd.to_datetime(W.t - 900, unit="s", utc=True).dt.floor("D")
near_whale = pd.DataFrame(False, index=DAYS, columns=circ.columns)
for r in W.itertuples():
    if r.s in near_whale.columns:
        near_whale.loc[r.d - pd.Timedelta(days=1): r.d + pd.Timedelta(days=1), r.s] = True


def flt(e, *masks):
    out = e.copy()
    for m in masks:
        out = out & m.reindex(index=out.index, columns=out.columns).fillna(False)
    return out


cands = {
    "Г1 рывок Binance без нашего крупного завода, спокойный день": o4u,
    "Г2 спящие ≥ 1 года ≥ 0,5% вне разлоков ±3 сут и 🐋 ±1 сут, спокойный день":
        flt(EV["O2 спящие 365d"], ~near_unlock, ~near_whale, calm),
    "Г2b age consumed z ≥ 3 вне разлоков и 🐋, спокойный день": flt(EV["O1 age consumed"], ~near_unlock, ~near_whale, calm),
    "Г2c age consumed z ≥ 3 вне разлоков, BEP20 и прочие сети, спокойный день":
        flt(EV["O1 age consumed"][[s for s in EV["O1 age consumed"].columns if infra.get(s) != "ETH"]], ~near_unlock, calm),
    "Г3 тренды Santiment, первый за 30 сут, спокойный день": flt(EV["S3 в трендах Santiment"], calm),
    "Г3b соцобъём z ≥ 3 в спокойный день (внимание без хода цены)": flt(EV["S1 соцобъём ×"], calm),
    "Г4 только Telegram (без Twitter и Reddit)": EV["S4 только Telegram"],
    "Г5 активные адреса пополнения z ≥ 3, спокойный день": flt(EV["O5 активные адреса пополнения"], calm),
    "Г6 MVRV30 пересёк 1,3": EV["O7 MVRV30 ≥ 1,3"],
}
for k, e in cands.items():
    show(k, e)
pickle.dump({"cands": cands, "o4cat": C}, open(f"{D}/cands.pkl", "wb"))
