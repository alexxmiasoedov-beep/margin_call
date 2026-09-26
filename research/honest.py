"""Честный бэктест без заглядывания в будущее.
Сигнал: серия >=4ч (разрывы <=30 мин); движение за 4ч = open свечи сигнала / close свечи 16 барами раньше.
Правило 1: +8..+17%. Правило 2: -8..-17% и B/R>=5. Общий кулдаун 24ч по монете. Вход по open свечи сигнала.
Тейк/стоп проверяются начиная с самой свечи сигнала, при попадании обоих в одну свечу — стоп. Выход по времени через 24ч по close.
Комиссия тейкера 0.05% x2 от номинала. Маржа 1 USDT, плечо 10."""
import json, glob, os, bisect, sys
import numpy as np, pandas as pd
pd.set_option("display.width", 200)

MARGIN, LEV, FEE = 1.0, 10, 0.0005
GAP, MIN_RUN, PMIN, PMAX, BR_MIN, HOLD = 1800, 4.0, 8, 17, 5, 96

df = pd.read_csv("dataset.csv", usecols=["sym", "epoch", "br"]).sort_values(["sym", "epoch"])
df["gap"] = df.groupby("sym").epoch.diff()
df["run_id"] = ((df.gap.isna()) | (df.gap > GAP)).groupby(df.sym).cumsum()
df["run_h"] = (df.epoch - df.groupby(["sym", "run_id"]).epoch.transform("min")) / 3600
df = df[df.run_h >= MIN_RUN]

K = {}
for fn in glob.glob("klines/*.json"):
    s = os.path.basename(fn)[:-5]
    k = np.array(json.load(open(fn))["k"], dtype=float)
    if len(k) < 200 or k[:, 4].std() / k[:, 4].mean() < 0.002: continue
    K[s] = (k[:, 0].astype(int), k[:, 1], k[:, 2], k[:, 3], k[:, 4])   # t, open, high, low, close
df = df[df.sym.isin(K)].sort_values("epoch")

# отбор сигналов
sig = []; last = {}
for r in df.itertuples():
    t, o, h, l, c = K[r.sym]
    i = bisect.bisect_right(t, r.epoch) - 1
    if i < 17 or i + 1 >= len(t): continue
    b4h = (o[i] / c[i - 16] - 1) * 100          # цена сейчас (открытие текущей свечи) против 4ч назад
    rule = "1" if PMIN <= b4h <= PMAX else ("2" if -PMAX <= b4h <= -PMIN and r.br >= BR_MIN else None)
    if not rule: continue
    if r.sym in last and r.epoch - last[r.sym] < 86400: continue
    last[r.sym] = r.epoch
    end = min(i + HOLD, len(t) - 1)
    sig.append((r.sym, r.epoch, rule, b4h, o[i], h[i:end + 1] / o[i] * 100 - 100, l[i:end + 1] / o[i] * 100 - 100, (c[end] / o[i] - 1) * 100, end - i))
print(f"сигналов {len(sig)}: правило 1 {sum(1 for s in sig if s[2]=='1')}, правило 2 {sum(1 for s in sig if s[2]=='2')}")


def run(tp, sl, sel=None):
    rows = []
    for sym, ep, rule, b4h, e, H, L, ret24, nb in sig:
        if sel and not sel(rule, ep): continue
        res = None; hrs = nb / 4
        for j, (hh, ll) in enumerate(zip(H, L)):
            if hh >= sl: res, kind, hrs = -sl / 10, "стоп", j / 4; break
            if ll <= -tp: res, kind, hrs = tp / 10, "тейк", j / 4; break
        if res is None: res, kind = -ret24 / 10, ("время" if nb >= HOLD else "обрыв")
        res -= MARGIN * LEV * FEE * 2
        rows.append((ep, rule, kind, res, hrs))
    x = pd.DataFrame(rows, columns=["epoch", "rule", "исход", "pnl", "часов"])
    return x


def summary(x, label):
    eq = x.pnl.cumsum(); dd = (eq - eq.cummax()).min(); mid = x.epoch.median()
    vc = x.исход.value_counts(normalize=True) * 100
    return (f"{label:10s} n={len(x)} тейк {vc.get('тейк',0):3.0f}% стоп {vc.get('стоп',0):3.0f}% время {vc.get('время',0):3.0f}% | итого {x.pnl.sum():+7.1f} "
            f"(1-я {x[x.epoch<mid].pnl.sum():+5.1f} / 2-я {x[x.epoch>=mid].pnl.sum():+5.1f}) | на сделку {x.pnl.mean():+.3f} | просадка {dd:+.1f}")


print("\n== ЧЕСТНО, маржа 1 USDT, с комиссиями; оба правила ==")
for tp in (8, 10):
    for sl in (16, 18, 20, 23, 25):
        print(summary(run(tp, sl), f"тейк {tp} стоп {sl}"))
print("\n== по правилам ==")
for rule in ("1", "2"):
    for tp, sl in ((8, 16), (10, 20), (10, 23), (10, 25)):
        print(f"правило {rule}: " + summary(run(tp, sl, lambda r, e, rule=rule: r == rule), f"{tp}/{sl}"))
print("\n== по месяцам: 8/16, 10/20, 10/23, 10/25 ==")
cols = {}
for tp, sl in ((8, 16), (10, 20), (10, 23), (10, 25)):
    x = run(tp, sl); x["m"] = pd.to_datetime(x.epoch, unit="s").dt.strftime("%Y-%m"); cols[f"{tp}/{sl}"] = x.groupby("m").pnl.sum().round(1)
print(pd.DataFrame(cols).to_string())
x = run(10, 23); x["day"] = pd.to_datetime(x.epoch, unit="s").dt.date
print(f"\n10/23: худший день {x.groupby('day').pnl.sum().min():+.1f}, лучший {x.groupby('day').pnl.sum().max():+.1f}, дней в минусе {(x.groupby('day').pnl.sum()<0).mean()*100:.0f}%, средняя длительность {x.часов.mean():.1f} ч")
