"""s201: крайние события по метрикам Santiment — частоты в месяц на вселенную перпов и пересечения с нашими событиями.

Без доходов: только сам день события. Описание дня — ход закрытия перпа к прошлому закрытию (r_cc) на день события
(«памп-день» ≥ +10%, «обвал-день» ≤ −10%) — как разрешено для описания.

z — к своей истории: z = (log1p(x_D) − среднее за D−30…D−1) / ст. откл. (не меньше 0,2), не меньше 20 дней истории.
Событие — первый день условия за 7 сут (новая вспышка), перп торговался в этот день.
Половины: H1 до 2026-05-01, H2 с 2026-05-01. Итог: events.log, /home/user/mc_data/s201/events.pkl."""
import pickle

import numpy as np
import pandas as pd

D = "/home/user/mc_data/s201"
P = pickle.load(open(f"{D}/panel.pkl", "rb"))
DAYS = P["social_volume_total"].index
CUT = pd.Timestamp("2026-05-01", tz="UTC")
circ = P["circ"]
qv = P["perp_qv"]
traded = qv.fillna(0) > 0
c = P["perp_c"]
r_cc = c / c.shift(1) - 1
pump, dump = r_cc >= 0.10, r_cc <= -0.10


def zlog(x, win=30, minp=20, floor=0.2):
    lx = np.log1p(x.clip(lower=0))
    b = lx.shift(1)
    m = b.rolling(win, min_periods=minp).mean()
    sd = b.rolling(win, min_periods=minp).std().clip(lower=floor)
    return (lx - m) / sd


def zraw(x, win=30, minp=20, floor=1e-9):
    b = x.shift(1)
    m = b.rolling(win, min_periods=minp).mean()
    sd = b.rolling(win, min_periods=minp).std().clip(lower=floor)
    return (x - m) / sd


def first_in(cond, k=7):
    cond = cond.fillna(False).astype(bool)
    prev = cond.shift(1).rolling(k, min_periods=1).max().fillna(0).astype(bool)
    return cond & ~prev


def align(*fr):
    cols = sorted(set.intersection(*[set(f.columns) for f in fr]))
    return [f.reindex(columns=cols) for f in fr]


EV, DEF = {}, {}


def add(name, cond, base_ok, text):
    cond, base_ok, tr = align(cond.fillna(False), base_ok.fillna(False), traded)
    e = first_in(cond & base_ok) & tr
    EV[name] = e
    DEF[name] = (text, int(base_ok.any().sum()), base_ok & tr)


sv = P["social_volume_total"]
zsv = zlog(sv)
add("S1 соцобъём ×", (zsv >= 3) & (sv >= 20), zsv.notna(), "social_volume_total: z ≥ 3 и ≥ 20 упоминаний")
add("S1b соцобъём × сильный", (zsv >= 5) & (sv >= 50), zsv.notna(), "social_volume_total: z ≥ 5 и ≥ 50")
sd = P["social_dominance_total"]
zsd = zlog(sd * 100)
add("S2 доля обсуждения", (zsd >= 3) & (sv >= 20), zsd.notna(), "social_dominance_total: z ≥ 3 и объём ≥ 20")
tw = P["trending_words_rank"]
intr = tw.notna()
absent30 = ~intr.shift(1).rolling(30, min_periods=1).max().fillna(0).astype(bool)
okt = pd.DataFrame(True, index=DAYS, columns=tw.columns) & (pd.Series(np.arange(len(DAYS)) >= 30, index=DAYS).values[:, None])
add("S3 в трендах Santiment", intr & absent30, okt, "trending_words_rank: первый день в трендах после ≥ 30 сут вне их")
add("S3b тренды, топ-10", (tw <= 10) & absent30, okt, "trending_words_rank ≤ 10, первый за 30 сут")
tg, tt, rd, ch = (P[f"social_volume_{k}"] for k in ("telegram", "twitter", "reddit", "4chan"))
ztg, ztt, zrd, zch = (zlog(x) for x in (tg, tt, rd, ch))
add("S4 только Telegram", (ztg >= 3) & (tg >= 10) & (ztt < 1) & (zrd < 1), ztg.notna() & ztt.notna(),
    "Telegram z ≥ 3 и ≥ 10, у Twitter и Reddit z < 1")
add("S5 4chan", (zch >= 3) & (ch >= 5), zch.notna(), "4chan /biz/: z ≥ 3 и ≥ 5 постов")
add("S6 Twitter", (ztt >= 3) & (tt >= 10), ztt.notna(), "Twitter: z ≥ 3 и ≥ 10")
sw = P["sentiment_weighted_total"]
zsw = zraw(sw)
add("S7 эйфория", (zsw >= 3) & (sv >= 20), zsw.notna(), "sentiment_weighted_total: z ≥ 3 (сырой), объём ≥ 20")

ac = P["age_consumed"]
zac = zlog(ac)
add("O1 age consumed", zac >= 3, zac.notna(), "age_consumed: z ≥ 3")
add("O1b age consumed сильный", zac >= 5, zac.notna(), "age_consumed: z ≥ 5")
for k, thr in (("365d", 0.005), ("90d", 0.01)):
    dc = P[f"dormant_circulation_{k}"]
    sh = dc / circ.reindex(columns=dc.columns)
    zdc = zlog(dc)
    add(f"O2 спящие {k}", (sh >= thr) & (zdc >= 3), zdc.notna() & sh.notna(),
        f"dormant_circulation_{k} ≥ {thr*100:.1f}% обращения и z ≥ 3")
ei = P["exchange_inflow"]
shi = ei / circ.reindex(columns=ei.columns)
zei = zlog(ei)
add("O3 приток на биржи", (zei >= 3) & (shi >= 0.005), zei.notna() & shi.notna(), "exchange_inflow: z ≥ 3 и ≥ 0,5% обращения")
bn = P["labelled_historical_balance__binance"]
dbn = bn.diff() / circ.reindex(columns=bn.columns)
add("O4 Binance +0,5%", dbn >= 0.005, dbn.notna(), "баланс меток owner->binance вырос за сутки ≥ 0,5% обращения")
add("O4b Binance +1%", dbn >= 0.01, dbn.notna(), "то же, ≥ 1% обращения")
ad = P["active_deposits"]
zad = zlog(ad)
add("O5 активные адреса пополнения", (zad >= 3) & (ad >= 20), zad.notna(), "active_deposits: z ≥ 3 и ≥ 20 адресов")
wt = P["whale_transaction_count_1m_usd_to_inf"]
zwt = zlog(wt)
add("O6 сделки китов ≥ 1 млн $", (zwt >= 3) & (wt >= 3), zwt.notna(), "whale_transaction_count_1m_usd_to_inf: z ≥ 3 и ≥ 3")
w1 = P["whale_transaction_count_100k_usd_to_inf"]
zw1 = zlog(w1)
add("O6b сделки китов ≥ 100 тыс. $", (zw1 >= 3) & (w1 >= 5), zw1.notna(), "whale_transaction_count_100k_usd_to_inf: z ≥ 3 и ≥ 5")
mv = P["mvrv_usd_30d"].where(P["mvrv_usd_30d"] > 0)
below14 = (mv.shift(1) < 1.3).rolling(14, min_periods=14).min().fillna(0).astype(bool)
add("O7 MVRV30 ≥ 1,3", (mv >= 1.3) & below14, mv.notna(), "mvrv_usd_30d пересёк 1,3 снизу (14 сут ниже)")
below14b = (mv.shift(1) < 1.5).rolling(14, min_periods=14).min().fillna(0).astype(bool)
add("O7b MVRV30 ≥ 1,5", (mv >= 1.5) & below14b, mv.notna(), "mvrv_usd_30d пересёк 1,5 снизу")
md = P["mean_dollar_invested_age"].where(P["mean_dollar_invested_age"] > 0)
mch = md / md.shift(1) - 1
add("O8 MDIA −10%", mch <= -0.10, mch.notna(), "mean_dollar_invested_age упал за сутки ≥ 10% (двинулись старые деньги)")
ng = P["network_growth"]
zng = zlog(ng)
add("O9 новые адреса", (zng >= 3) & (ng >= 50), zng.notna(), "network_growth: z ≥ 3 и ≥ 50 новых адресов")
daa = P["daily_active_addresses"]
zda = zlog(daa)
add("O10 активные адреса", (zda >= 3) & (daa >= 50), zda.notna(), "daily_active_addresses: z ≥ 3 и ≥ 50")

# --- наши события в окне ---
d0, d1 = DAYS[0] + pd.Timedelta(days=20), DAYS[-1]
U = pd.read_pickle("/home/user/mc_data/s142_2024–2026.pkl")[["s", "T"]]
U["d"] = pd.to_datetime(U["T"], unit="s", utc=True).dt.floor("D")
U = U[(U.d >= d0) & (U.d <= d1) & U.s.isin(circ.columns)].drop_duplicates(["s", "d"])
W = pd.read_pickle("/home/user/mc_data/s167lv_2024–2026.pkl")[["s", "t", "B", "r24"]]
W = W[W.B]
W["d"] = pd.to_datetime(W.t - 900, unit="s", utc=True).dt.floor("D")
W = W[(W.d >= d0) & (W.d <= d1) & W.s.isin(circ.columns)]
W["whale"] = W.r24.abs() <= 0.05
E160 = pd.read_pickle("/home/user/mc_data/s160_events.pkl")[["perp", "t", "exch", "frac"]]
E160["d"] = pd.to_datetime(E160.t, unit="s", utc=True).dt.floor("D")
E160 = E160[(E160.d >= d0) & (E160.d <= d1) & E160.perp.isin(circ.columns)]
dep_bn = E160[E160.exch == "Binance"].groupby(["perp", "d"]).frac.sum()
dep_all = E160.groupby(["perp", "d"]).frac.sum()

rows = []
months = lambda m: m.sum() / 30.44
for name, e in EV.items():
    text, ncov, base = DEF[name]
    days_ok = base.any(axis=1)
    h1 = e.index < CUT
    n, n1, n2 = int(e.values.sum()), int(e[h1].values.sum()), int(e[~h1].values.sum())
    m_all, m1, m2 = months(days_ok), months(days_ok & h1), months(days_ok & ~h1)
    pp, dd = align(e, pump.reindex(columns=e.columns))[1], align(e, dump.reindex(columns=e.columns))[1]
    ev_p = float(pp.where(e).stack().mean()) if n else np.nan
    ev_d = float(dd.where(e).stack().mean()) if n else np.nan
    bp = float(pp.where(base & traded.reindex(columns=e.columns)).stack().mean())
    bd = float(dd.where(base & traded.reindex(columns=e.columns)).stack().mean())
    pr = align(e, pump.shift(1).reindex(columns=e.columns))[1]
    ev_pp = float(pr.where(e).stack().mean()) if n else np.nan
    rows.append(dict(event=name, cover=ncov, n=n, per_month=n / m_all if m_all else np.nan,
                     h1=n1 / m1 if m1 else np.nan, h2=n2 / m2 if m2 else np.nan,
                     pump_day=ev_p, pump_base=bp, dump_day=ev_d, dump_base=bd, pump_prev=ev_pp, text=text))
T = pd.DataFrame(rows)
pd.set_option("display.width", 250)
print("Частоты событий (в месяц на всю вселенную, первые за 7 сут) и описание дня события")
print("cover — перпов с метрикой; pump_day — доля событий в день роста закрытия ≥ +10% (pump_base — у всех дней тех же"
      " перпов); dump — то же для −10%; pump_prev — памп был накануне")
print(T.drop(columns="text").to_string(index=False, float_format=lambda x: f"{x:.3f}" if abs(x) < 1 else f"{x:.1f}"))
print("\nОпределения:")
for r in T.itertuples():
    print(f"  {r.event}: {r.text}")


def window_hit(e, s, d, lo, hi):
    if s not in e.columns:
        return np.nan
    sl = e[s].loc[d + pd.Timedelta(days=lo): d + pd.Timedelta(days=hi)]
    return float(sl.any()) if len(sl) else np.nan


def enrich(events, keys, lo, hi, label):
    print(f"\n{label}: окно [{lo:+d}; {hi:+d}] сут к дню события; доля событий с меткой и случайная доля (те же перпы, все дни)")
    for name in keys:
        e = EV[name]
        hits = [window_hit(e, r.s, r.d, lo, hi) for r in events.itertuples()]
        hits = np.array([h for h in hits if h == h])
        if not len(hits):
            continue
        cols = [s for s in events.s.unique() if s in e.columns]
        base_rate = e[cols].rolling(hi - lo + 1, min_periods=1).max().stack().mean() if cols else np.nan
        print(f"  {name}: {hits.mean()*100:.1f}% из {len(hits)} (случайно {base_rate*100:.1f}%, ×{hits.mean()/base_rate:.1f})"
              if base_rate else f"  {name}: {hits.mean()*100:.1f}% из {len(hits)}")


print(f"\n🔑⁺ разлоков в окне ({d0.date()} … {d1.date()}) у перпов вселенной: {len(U)}")
enrich(U, ["O1 age consumed", "O2 спящие 365d", "O2 спящие 90d", "O3 приток на биржи", "O4 Binance +0,5%",
           "O5 активные адреса пополнения", "O6 сделки китов ≥ 1 млн $", "O9 новые адреса"], 0, 2, "🔑⁺ разлок, ончейн")
enrich(U, ["S1 соцобъём ×", "S3 в трендах Santiment", "S4 только Telegram"], -7, 0, "🔑⁺ разлок, соцсети до разлока")
print(f"\n🐋 (правило бота B, все r24) в окне: {len(W)}, из них спокойный рынок |r24| ≤ 5%: {int(W.whale.sum())}")
enrich(W, ["O3 приток на биржи", "O4 Binance +0,5%", "O4b Binance +1%", "O5 активные адреса пополнения",
           "O6 сделки китов ≥ 1 млн $", "O1 age consumed", "O2 спящие 90d"], 0, 0, "🐋 завод на Binance, тот же день")
enrich(W, ["O4 Binance +0,5%", "O3 приток на биржи"], -1, 1, "🐋 завод на Binance, ±1 сут")
enrich(W, ["S1 соцобъём ×", "S3 в трендах Santiment"], -3, 0, "🐋 завод, соцсети за 3 сут до")

# обратная сверка меток: события Santiment ↔ наши заводы (s160, ≥ 0,5% обращения, все кроме кастоди)
for name, dep in (("O4 Binance +0,5%", dep_bn), ("O3 приток на биржи", dep_all)):
    e = EV[name]
    st = e.stack()
    st = st[st]
    hit = []
    for (d, s) in st.index:
        h = any((s, d + pd.Timedelta(days=k)) in dep.index for k in (-1, 0))
        hit.append(h)
    print(f"\n{name}: событий {len(hit)}, у {np.mean(hit)*100:.1f}% есть наш завод ≥ 0,5% обращения "
          f"({'на Binance' if dep is dep_bn else 'на любые биржи'}) в тот же или предыдущий день")
cov = set(bn.columns)
db = dep_bn.reset_index()
db = db[db.perp.isin(cov)]
got = [bool(EV["O4 Binance +0,5%"][r.perp].loc[r.d: r.d + pd.Timedelta(days=1)].any()) for r in db.itertuples()]
print(f"Наши дни заводов на Binance (≥ 0,5%) у перпов с меткой Santiment: {len(got)}, из них видны как O4 в тот же или "
      f"следующий день: {np.mean(got)*100:.1f}%")
bal_change = []
for r in db.itertuples():
    v = dbn[r.perp].loc[r.d: r.d + pd.Timedelta(days=1)].max() if r.perp in dbn.columns else np.nan
    bal_change.append((r.frac, v))
bc = pd.DataFrame(bal_change, columns=["frac", "dbal"]).dropna()
print(f"  медиана Δ баланса Binance (доля обращения) в дни наших заводов: {bc.dbal.median()*100:.3f}% при медиане завода "
      f"{bc.frac.median()*100:.2f}%; доля дней с Δ ≥ половины завода: {(bc.dbal >= 0.5*bc.frac).mean()*100:.1f}%")

pickle.dump({"EV": EV, "T": T}, open(f"{D}/events.pkl", "wb"))
