"""Бэктест с учётом фандинга (Gate, с 06.04.2026): сколько фандинг съедает и какие правила защищают."""
import json, glob, os, bisect, time
import numpy as np, pandas as pd
pd.set_option("display.width", 220)

MARGIN, LEV, FEE = 1.0, 10, 0.0005
NOTIONAL = MARGIN * LEV
GAP, MIN_RUN, PMIN, PMAX, BR_MIN, PAUSE = 1800, 4.0, 8, 17, 5, 48 * 3600
FUND = {s: (np.array([x[0] for x in v]), np.array([x[1] for x in v])) for s, v in json.load(open("funding_gate.json")).items()}
T0 = min(v[0][0] for v in FUND.values()) + 86400

df = pd.read_csv("dataset.csv", usecols=["sym", "epoch", "br"]).sort_values(["sym", "epoch"])
df["gap"] = df.groupby("sym").epoch.diff(); df["run_id"] = ((df.gap.isna()) | (df.gap > GAP)).groupby(df.sym).cumsum()
df["run_h"] = (df.epoch - df.groupby(["sym", "run_id"]).epoch.transform("min")) / 3600
df = df[(df.run_h >= MIN_RUN) & (df.epoch >= T0)]
K = {}
for fn in glob.glob("klines/*.json"):
    s = os.path.basename(fn)[:-5]
    if s not in FUND: continue
    k = np.array(json.load(open(fn))["k"], dtype=float)
    if len(k) < 200: continue
    K[s] = (k[:, 0].astype(int), k[:, 1], k[:, 2], k[:, 3], k[:, 4])
df = df[df.sym.isin(K)].sort_values("epoch")
cands = []
for r in df.itertuples():
    t, o, h, l, c = K[r.sym]; i = bisect.bisect_right(t, r.epoch) - 1
    if i < 20 or i + 1 >= len(t): continue
    b4h = (o[i] / c[i - 16] - 1) * 100
    rule = "1" if PMIN <= b4h <= PMAX else ("2" if -PMAX <= b4h <= -PMIN and r.br >= BR_MIN else None)
    if rule: cands.append((r.sym, int(r.epoch), rule, i))
mid = np.median([c_[1] for c_ in cands])


def hourly_rate_at(sym, ts):
    """Последний начисленный фандинг до ts в пересчёте на час (доля), и интервал в часах."""
    ft, fr = FUND[sym]; k = bisect.bisect_right(ft, ts) - 1
    if k < 1: return None, None
    iv = max((ft[k] - ft[k - 1]) / 3600, 1)
    return fr[k] / iv, iv


def run(tp, sl, hold_h=48, entry_max=None, exit_rate=None, exit_cum=None, with_funding=True):
    """entry_max: не входить, если фандинг/час < −entry_max (%). exit_rate: выйти на начислении, если ставка/час ≤ −exit_rate (%).
    exit_cum: выйти, если накопленный уплаченный фандинг ≥ exit_cum % номинала."""
    last = {}; open_until = {}; last_stop = {}; rows = []
    for sym, ep, rule, i in cands:
        if sym in last and ep - last[sym] < 86400: continue
        if sym in open_until and open_until[sym] > ep: continue
        last[sym] = ep
        if sym in last_stop and ep - last_stop[sym] < PAUSE: continue
        rh, iv = hourly_rate_at(sym, ep)
        if entry_max is not None and rh is not None and rh * 100 < -entry_max:
            rows.append((ep, rule, "пропуск", 0.0, 0.0, 0.0, rh)); continue
        t, o, h, l, c = K[sym]; ft, fr = FUND[sym]; e = o[i]; end = min(i + hold_h * 4, len(t) - 1)
        fk = bisect.bisect_right(ft, ep); fund = 0.0; res = None
        for j in range(i, end + 1):
            if h[j] >= e * (1 + sl / 100): res, kind, xj = -sl / 100 * NOTIONAL, "стоп", j; break
            if tp and l[j] <= e * (1 - tp / 100): res, kind, xj = tp / 100 * NOTIONAL, "тейк", j; break
            bar_end = t[j] + 900; cut = False
            while fk < len(ft) and ft[fk] <= bar_end:
                if with_funding: fund += fr[fk] * NOTIONAL          # шорт получает при r>0, платит при r<0
                ivh = max((ft[fk] - ft[fk - 1]) / 3600, 1) if fk > 0 else 8
                if exit_rate is not None and fr[fk] / ivh * 100 <= -exit_rate: cut = True
                fk += 1
            if exit_cum is not None and -fund / NOTIONAL * 100 >= exit_cum: cut = True
            if cut:
                res, kind, xj = -(c[j] / e - 1) * NOTIONAL, "выход по фандингу", j; break
        if res is None: res, kind, xj = -(c[end] / e - 1) * NOTIONAL, "время", end
        pnl = res + fund - NOTIONAL * FEE * 2
        hrs = (xj - i) / 4; open_until[sym] = ep + hrs * 3600
        if kind == "стоп": last_stop[sym] = ep + hrs * 3600
        rows.append((ep, rule, kind, pnl, fund, hrs, rh))
    return pd.DataFrame(rows, columns=["ep", "rule", "k", "pnl", "fund", "hrs", "rh"])


def rep(x, label):
    x = x[x.k != "пропуск"]; a = x[x.ep < mid]; b = x[x.ep >= mid]; eq = x.pnl.cumsum(); dd = (eq - eq.cummax()).min()
    vc = x.k.value_counts(normalize=True) * 100
    print(f"  {label:58s} n={len(x):3d} тейк {vc.get('тейк',0):3.0f}% стоп {vc.get('стоп',0):3.0f}% фанд-выход {vc.get('выход по фандингу',0):3.0f}% | итого {x.pnl.sum():+6.1f} ({a.pnl.sum():+5.1f}/{b.pnl.sum():+5.1f}) | фандинг {x.fund.sum():+5.1f} | просадка {dd:+5.1f}")


print(f"сигналов с {time.strftime('%d.%m', time.gmtime(T0))}: {len(cands)}")
for tp, sl, name in ((6, 20, "СЕЙЧАС: тейк 6 / стоп 20 / 48 ч"), (None, 25, "ВИРТУАЛЬНЫЙ: без тейка / стоп 25 / 48 ч")):
    print(f"\n==================== {name} ====================")
    base = run(tp, sl, with_funding=False); fund = run(tp, sl)
    rep(base, "без учёта фандинга (как считали раньше)")
    rep(fund, "С УЧЁТОМ ФАНДИНГА")
    f = fund[fund.k != "пропуск"]
    print(f"  фандинг на сделку: медиана {f.fund.median():+.3f}, хуже −0,2 USDT в {(f.fund < -0.2).mean()*100:.0f}% сделок, хуже −0,5 в {(f.fund < -0.5).mean()*100:.0f}%, хуже −1 в {(f.fund < -1).mean()*100:.0f}%; худшая {f.fund.min():+.2f}")
    f = f.assign(b=pd.cut(f.rh * 100, [-99, -0.2, -0.1, -0.05, -0.02, 0, 99], labels=["< −0,2%/ч", "−0,2…−0,1", "−0,1…−0,05", "−0,05…−0,02", "−0,02…0", "≥ 0"]))
    g = f.groupby("b", observed=True).agg(n=("pnl", "size"), pnl=("pnl", "mean"), сумма=("pnl", "sum"), фандинг=("fund", "mean"), стоп=("k", lambda s: (s == "стоп").mean() * 100))
    print("  по фандингу в момент входа (ставка в час):\n  " + g.round(2).to_string().replace("\n", "\n  "))
    print("  -- правила --")
    for em in (0.2, 0.1, 0.05):
        rep(run(tp, sl, entry_max=em), f"не входить при фандинге < −{em}%/ч")
    for er in (0.2, 0.1, 0.05):
        rep(run(tp, sl, exit_rate=er), f"выйти, если начисление < −{er}%/ч")
    for ec in (1, 2, 3):
        rep(run(tp, sl, exit_cum=ec), f"выйти, если уплачено фандинга ≥ {ec}% номинала")
    rep(run(tp, sl, entry_max=0.1, exit_rate=0.1), "вход < −0,1%/ч нет + выход при < −0,1%/ч")
    rep(run(tp, sl, entry_max=0.1, exit_cum=2), "вход < −0,1%/ч нет + выход при уплате ≥ 2%")


def run2(sl=25, hold_h=48, tp_when_neg=None, neg_th=0.05, extreme_exit=None, short_hold=None):
    """Без тейка, но: tp_when_neg — тейк включается, если последнее начисление < −neg_th %/ч;
    extreme_exit — выход, если начисление ≤ −extreme_exit %/ч; short_hold=(порог %/ч, часов) — укороченное удержание при входе в сильный минус."""
    last = {}; open_until = {}; last_stop = {}; rows = []
    for sym, ep, rule, i in cands:
        if sym in last and ep - last[sym] < 86400: continue
        if sym in open_until and open_until[sym] > ep: continue
        last[sym] = ep
        if sym in last_stop and ep - last_stop[sym] < PAUSE: continue
        rh, _ = hourly_rate_at(sym, ep)
        hh = hold_h
        if short_hold and rh is not None and rh * 100 < -short_hold[0]: hh = short_hold[1]
        t, o, h, l, c = K[sym]; ft, fr = FUND[sym]; e = o[i]; end = min(i + hh * 4, len(t) - 1)
        fk = bisect.bisect_right(ft, ep); fund = 0.0; res = None
        neg = rh is not None and rh * 100 < -neg_th
        for j in range(i, end + 1):
            if h[j] >= e * (1 + sl / 100): res, kind, xj = -sl / 100 * NOTIONAL, "стоп", j; break
            if tp_when_neg and neg and l[j] <= e * (1 - tp_when_neg / 100): res, kind, xj = tp_when_neg / 100 * NOTIONAL, "тейк", j; break
            bar_end = t[j] + 900; cut = False
            while fk < len(ft) and ft[fk] <= bar_end:
                fund += fr[fk] * NOTIONAL
                ivh = max((ft[fk] - ft[fk - 1]) / 3600, 1) if fk > 0 else 8
                hr = fr[fk] / ivh * 100
                neg = hr < -neg_th
                if extreme_exit is not None and hr <= -extreme_exit: cut = True
                fk += 1
            if cut: res, kind, xj = -(c[j] / e - 1) * NOTIONAL, "выход по фандингу", j; break
        if res is None: res, kind, xj = -(c[end] / e - 1) * NOTIONAL, "время", end
        pnl = res + fund - NOTIONAL * FEE * 2
        hrs = (xj - i) / 4; open_until[sym] = ep + hrs * 3600
        if kind == "стоп": last_stop[sym] = ep + hrs * 3600
        rows.append((ep, rule, kind, pnl, fund, hrs, rh))
    return pd.DataFrame(rows, columns=["ep", "rule", "k", "pnl", "fund", "hrs", "rh"])


print("\n==================== УМНЫЕ ПРАВИЛА для «без тейка / стоп 25» ====================")
rep(run2(), "база (с фандингом)")
for th in (0.02, 0.05, 0.1):
    for tp in (6, 8):
        rep(run2(tp_when_neg=tp, neg_th=th), f"тейк {tp}% включается, пока фандинг < −{th}%/ч")
for ex in (0.3, 0.4, 0.5):
    rep(run2(extreme_exit=ex), f"выход только при экстремальном фандинге ≤ −{ex}%/ч")
for th, hh in ((0.1, 12), (0.1, 24), (0.2, 12), (0.05, 24)):
    rep(run2(short_hold=(th, hh)), f"держать {hh} ч, если на входе фандинг < −{th}%/ч")
rep(run2(tp_when_neg=6, neg_th=0.05, extreme_exit=0.4), "тейк 6 при фандинге < −0,05%/ч + выход при ≤ −0,4%/ч")
print("\n==================== то же для «тейк 6 / стоп 20» ====================")
for ex in (0.3, 0.4):
    rep(run(6, 20, exit_rate=ex), f"тейк 6: выход при начислении ≤ −{ex}%/ч")
