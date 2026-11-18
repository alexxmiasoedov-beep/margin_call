# Проверка механизма (только объёмы, без доходностей): есть ли след окна NAV 15:00-16:00 ET
# в часовом обороте Coinbase у монет с американскими спотовыми ETF до и после запуска.
import pickle, sys, numpy as np, pandas as pd
from zoneinfo import ZoneInfo
d = pickle.load(open(sys.argv[1], 'rb'))
ETF = {  # первый спотовый ETF (1933 Act) в США; источники в отчёте
 'SOL': '2025-10-28', 'LTC': '2025-10-28', 'HBAR': '2025-10-28', 'XRP': '2025-11-13',
 'DOGE': '2025-11-24', 'LINK': '2025-12-02', 'AVAX': '2026-01-26', 'SUI': '2026-02-18',
 'DOT': '2026-03-06', 'HYPE': '2026-05-12', 'NEAR': '2026-09-24', 'TRX': '2026-09-08'}
NY = ZoneInfo('America/New_York')
def prep(df):
    df = df[df.usd > 0].copy()
    ts = pd.to_datetime(df['T'], unit='s', utc=True).dt.tz_convert(NY)
    df['nyh'] = ts.dt.hour; df['nyd'] = ts.dt.date
    return df
def fix_stats(df):
    # доля часа 15-16 ET в обороте суток NY и отношение к соседним часам (13-15 и 16-18 ET)
    g = df.groupby('nyd')
    tot = g.usd.sum()
    fx = df[df.nyh == 15].groupby('nyd').usd.sum()
    nb = df[df.nyh.isin([13, 14, 16, 17])].groupby('nyd').usd.sum() / 4
    j = pd.concat([tot, fx, nb], axis=1, keys=['tot', 'fx', 'nb']).dropna()
    j = j[(j.tot > 0) & (j.nb > 0)]
    return j
rows = []
res = {}
for c, df in d.items():
    df = prep(df)
    if len(df) < 24 * 200: continue
    j = fix_stats(df)
    res[c] = j
cut_all = pd.Timestamp('2025-10-28').date()
def summ(j, lo, hi):
    k = j[(j.index >= lo) & (j.index < hi)]
    if len(k) < 30: return None
    return (k.fx.sum() / k.tot.sum(), (k.fx / k.nb).median(), len(k))
print("Монета    | доля часа 15-16 ET в сутках: до → после | отношение к соседним часам (медиана): до → после | дней до/после")
out = []
for c, l in ETF.items():
    if c not in res: print(c, 'нет на Coinbase'); continue
    j = res[c]; L = pd.Timestamp(l).date()
    lo = pd.Timestamp(L) - pd.Timedelta(days=180); hi = pd.Timestamp(L) + pd.Timedelta(days=180)
    a = summ(j, lo.date(), L); b = summ(j, (pd.Timestamp(L) + pd.Timedelta(days=7)).date(), hi.date())
    if a and b:
        out.append((c, a, b))
        print(f"{c:6s} {l} | {100*a[0]:5.2f}% → {100*b[0]:5.2f}% | {a[1]:5.2f} → {b[1]:5.2f} | {a[2]}/{b[2]}")
# контроль: монеты без американского спотового ETF, тот же календарь (до/после 28.10.2025)
ctrl = [c for c in res if c not in ETF and c not in ('BTC', 'ETH', 'USDT', 'USDC', 'DAI', 'PYUSD', 'EURC')]
ca, cb = [], []
for c in ctrl:
    j = res[c]
    a = summ(j, pd.Timestamp('2025-05-01').date(), pd.Timestamp('2025-10-28').date())
    b = summ(j, pd.Timestamp('2025-11-04').date(), pd.Timestamp('2026-04-26').date())
    if a and b and j.tot.mean() > 2e5:
        ca.append(a[1]); cb.append(b[1])
print(f"Контроль ({len(ca)} монет без ETF, оборот Coinbase > $0,2M в сутки): отношение к соседним часам медиана {np.median(ca):.2f} → {np.median(cb):.2f}")
for c in ('BTC', 'ETH'):
    if c in res:
        j = res[c]
        a = summ(j, pd.Timestamp('2024-10-01').date(), pd.Timestamp('2025-10-01').date()); b = summ(j, pd.Timestamp('2025-10-01').date(), pd.Timestamp('2026-10-01').date())
        print(f"{c} (ETF с 2024 г.): доля часа 15-16 ET {100*a[0]:.2f}% / {100*b[0]:.2f}%, отношение к соседним {a[1]:.2f} / {b[1]:.2f}")
# Дифф-в-диффе по отношению к соседним часам
de = [b[1] - a[1] for c, a, b in out]
print(f"ETF-монеты: изменение отношения после запуска, медиана {np.median(de):+.2f} (по монетам {', '.join(f'{c} {b[1]-a[1]:+.2f}' for c,a,b in out)}); контроль {np.median(np.array(cb)-np.array(ca)):+.2f}")
