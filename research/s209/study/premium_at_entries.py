#!/usr/bin/env python3
"""s209: какая доля входов корейских журналов (🔝 s65, 👀 s83, ⏰ s88) приходится на высокую премию монеты на Upbit.

Только время и монета входа (колонки s, t); колонки доходов не читаются. Премия — дневная запись Upbit
за последние ЗАКРЫТЫЕ сутки до входа (запись дня D известна в 24:00 UTC D), поле usdt_real
(премия монеты сверх премии USDT, п. п.). Окно: входы с 20.06.2024.
"""
import bisect, collections, csv, gzip
from datetime import datetime, timezone
import pandas as pd

P = collections.defaultdict(list)
with gzip.open("/home/user/mc_data/s209/upbit_premium_DAYS_1.csv.gz", "rt") as f:
    for r in csv.DictReader(f):
        if r["usdt_real"] in ("", "None"):
            continue
        t = datetime.fromisoformat(r["time_utc"]).replace(tzinfo=timezone.utc).timestamp() + 86400
        P[r["market"][4:]].append((t, float(r["usdt_real"])))
for k in P:
    P[k].sort()


def prem(sym, t):
    for s in (sym, sym.replace("1000", "")):
        L = P.get(s)
        if L:
            i = bisect.bisect_right([x[0] for x in L], t) - 1
            if i >= 0 and t - L[i][0] < 2 * 86400:
                return L[i][1]
    return None


def show(name, df):
    df = df[df.t >= datetime(2024, 6, 20, tzinfo=timezone.utc).timestamp()]
    v = [prem(s, t) for s, t in zip(df.s, df.t)]
    have = [x for x in v if x is not None]
    n = len(df)
    m = (df.t.max() - df.t.min()) / 86400 / 30.44
    print(f"{name}: входов {n} ({n/m:.1f} в мес.), с премией Upbit {len(have)}")
    for lo in (0.5, 1, 2):
        k = sum(1 for x in have if x >= lo)
        print(f"   usdt_real ≥ +{lo} п. п.: {k} ({k/max(1,len(have)):.0%}, {k/m:.1f} в мес.)")
    k = sum(1 for x in have if x <= -0.5)
    print(f"   usdt_real ≤ −0,5 п. п.: {k} ({k/max(1,len(have)):.0%})")


kt = pd.read_pickle("/home/user/mc_data/s65/trades.pkl")[["s", "t"]]
rt = pd.read_pickle("/home/user/mc_data/s83/trades.pkl")[["s", "t"]]
o9 = pd.read_pickle("/home/user/mc_data/s88/trades.pkl")[["s", "t", "open9", "r1", "share"]]
o9 = o9[(o9.open9) & (o9.r1 >= 0.05) & (o9.share >= 0.20)][["s", "t"]]
show("🔝 (s65)", kt)
show("👀 (s83)", rt)
show("⏰ (s88, open9 & r1 ≥ 5% & доля ≥ 20%)", o9)
