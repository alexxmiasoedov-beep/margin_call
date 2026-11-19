"""s201: итоговые частоты гипотез (в месяц, H1 до 2026-05-01 / H2 после) и уточнения без доходов:
- Г2 тренды: ранг ≤ 10 первый за 14 сут, без 10 самых обсуждаемых монет, без дня пампа/обвала (|r_cc| ≤ 10%);
- Г3 спящие: без «системных» дней (≥ 3 монеты в один день), вне разлоков ±3 сут и 🐋 ±1 сут, спокойный день;
- Г4 волна пополнений: active_deposits z ≥ 3 в спокойный день; пересечение с дробью за час (s195) и рывками Binance;
- Г1 дробь за час на своём сборе: доля в спокойном рынке (|r_cc| накануне ≤ 5%) и пересечение с O5 и O4 Santiment."""
import pickle

import numpy as np
import pandas as pd

D = "/home/user/mc_data/s201"
P = pickle.load(open(f"{D}/panel.pkl", "rb"))
EV = pickle.load(open(f"{D}/events.pkl", "rb"))["EV"]
CA = pickle.load(open(f"{D}/cands.pkl", "rb"))["cands"]
DAYS = P["social_volume_total"].index
CUT = pd.Timestamp("2026-05-01", tz="UTC")
c = P["perp_c"]
r_cc = c / c.shift(1) - 1
traded = P["perp_qv"].fillna(0) > 0


def freq(e, start=20):
    days = e.index
    d0 = days[start]
    m1 = ((days >= d0) & (days < CUT)).sum() / 30.44
    m2 = (days >= CUT).sum() / 30.44
    n1 = int(e[(days >= d0) & (days < CUT)].values.sum())
    n2 = int(e[days >= CUT].values.sum())
    return n1 + n2, (n1 + n2) / (m1 + m2), n1 / m1, n2 / m2


def line(name, e, start=20):
    n, a, h1, h2 = freq(e, start)
    print(f"  {name}: {n} событий, {a:.1f}/мес (H1 {h1:.1f}, H2 {h2:.1f})")


# Г2 тренды
tw = P["trending_words_rank"]
sv = P["social_volume_total"]
majors = sv.mean().sort_values(ascending=False).head(10).index.tolist()
print("10 самых обсуждаемых (исключаются; среди них монеты с тикером-словом — их соцобъём засорён):", majors)
cond = tw <= 10
prev = cond.shift(1).rolling(14, min_periods=1).max().fillna(0).astype(bool)
e = (cond & ~prev & traded.reindex(columns=tw.columns).fillna(False))
e.iloc[:14] = False
e = e.drop(columns=[m for m in majors if m in e.columns])
quiet = r_cc.reindex(columns=e.columns).abs() <= 0.10
print("Г2 тренды Santiment:")
line("ранг ≤ 10, первый за 14 сут, без 10 лидеров", e, 14)
line("то же, день без пампа и обвала (|r_cc| ≤ 10%)", e & quiet.fillna(False), 14)
cond3 = tw <= 3
prev3 = cond3.shift(1).rolling(14, min_periods=1).max().fillna(0).astype(bool)
e3 = (cond3 & ~prev3 & traded.reindex(columns=tw.columns).fillna(False))
e3.iloc[:14] = False
e3 = e3.drop(columns=[m for m in majors if m in e3.columns])
line("ранг ≤ 3 (как «Peak Hype» Santiment), первый за 14 сут, без 10 лидеров", e3, 14)
sh = []
for k in (10, 3):
    ee = e if k == 10 else e3
    st = ee.stack()
    st = st[st]
    pv = np.mean([r_cc.at[d - pd.Timedelta(days=1), s] >= 0.10 for (d, s) in st.index if d > DAYS[0]])
    pd_ = np.mean([r_cc.at[d, s] >= 0.10 for (d, s) in st.index])
    print(f"    ранг ≤ {k}: в день памп ≥ +10% {pd_*100:.0f}%, накануне {pv*100:.0f}%")

# Г3 спящие
g3 = CA["Г2 спящие ≥ 1 года ≥ 0,5% вне разлоков ±3 сут и 🐋 ±1 сут, спокойный день"]
allo2 = EV["O2 спящие 365d"]
nday = allo2.sum(axis=1)
sysd = nday >= 3
print("\nГ3 спящие ≥ 1 года:")
print("  системных дней (≥ 3 монеты сразу):", int(sysd.sum()), "| в них событий O2:", int(allo2[sysd].values.sum()),
      "| крупнейшие:", ", ".join(f"{d.date()}:{int(n)}" for d, n in nday.sort_values(ascending=False).head(4).items()))
d_max = nday.idxmax()
print(f"  монеты дня {d_max.date()}:", sorted(allo2.columns[allo2.loc[d_max]].tolist()))
o4 = EV["O4 Binance +0,5%"]
same = (allo2 & o4.reindex(columns=allo2.columns).fillna(False)).values.sum()
print(f"  O2 в тот же день, что рывок Binance (O4): {int(same)} из {int(allo2.values.sum())}")
g3b = g3 & ~sysd.values[:, None]
line("вне разлоков и 🐋, спокойный день, без системных дней", g3b)

# Г4 волна пополнений
g4 = CA["Г5 активные адреса пополнения z ≥ 3, спокойный день"]
print("\nГ4 волна пополнений (active_deposits):")
line("z ≥ 3, ≥ 20 адресов, спокойный день", g4)
S1 = pd.read_pickle(f"{D}/split_1h.pkl")
S1["d"] = pd.to_datetime(S1.t, unit="s", utc=True).dt.floor("D")
S1w = S1[(S1.d >= DAYS[0]) & (S1.d <= DAYS[-1])]
sp = S1w[S1w.kind == "split"]
o5 = EV["O5 активные адреса пополнения"]
hit = [bool(o5[s].loc[d - pd.Timedelta(days=1): d].any()) if s in o5.columns else np.nan for s, d in zip(sp.perp, sp.d)]
hit = np.array([h for h in hit if h == h], float)
print(f"  дробь за час (наш сбор) в окне Santiment: {len(sp)}; с O5 в тот же или прошлый день: {hit.mean()*100:.0f}% из {len(hit)}")
hit4 = [bool(o4[s].loc[d: d + pd.Timedelta(days=1)].any()) if s in o4.columns else np.nan for s, d in zip(sp.perp, sp.d)]
hit4 = np.array([h for h in hit4 if h == h], float)
print(f"  дробь за час с рывком Binance (O4) в тот же или следующий день: {hit4.mean()*100:.0f}% из {len(hit4)}")

# Г1 на своём сборе — доля спокойного рынка (дневной ход накануне), по периодам
print("\nГ1 дробь за час на своём сборе (s195), доля событий при спокойном рынке накануне:")
import pickle as pk
U = pk.load(open(f"{D}/perp_daily.pkl", "rb"))["daily"]
cc = U.pivot_table(index="d", columns="s", values="c")
rr = cc / cc.shift(1) - 1
S1["dprev"] = S1.d - pd.Timedelta(days=1)
vals = []
for r in S1.itertuples():
    v = rr.at[r.dprev, r.perp] if (r.perp in rr.columns and r.dprev in rr.index) else np.nan
    vals.append(float(v) if v == v else np.nan)
S1["rprev"] = vals
s24 = S1[(S1.kind == "split") & S1.rprev.notna()]
print(f"  окно дневных свечей s201 (с 11.2025): дроблёных {len(s24)}, спокойно накануне (|ход| ≤ 5%) "
      f"{(s24.rprev.abs() <= 0.05).mean()*100:.0f}%")
