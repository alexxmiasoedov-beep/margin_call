# Частота триггера A1 (только подсчёт событий, без доходов сделок):
# ход монеты к BTC за час 15-16 ET (Coinbase, часовые закрытия) в торговые дни США после запуска ETF.
import pickle, sys, numpy as np, pandas as pd
from zoneinfo import ZoneInfo
d = pickle.load(open(sys.argv[1], 'rb'))
ETF = {'SOL': '2025-10-28', 'LTC': '2025-10-28', 'HBAR': '2025-10-28', 'XRP': '2025-11-13', 'DOGE': '2025-11-24',
       'LINK': '2025-12-02', 'AVAX': '2026-01-26', 'SUI': '2026-02-18', 'DOT': '2026-03-06', 'HYPE': '2026-05-12', 'NEAR': '2026-09-24'}
NY = ZoneInfo('America/New_York')
def closes(c):
    df = d[c]; s = pd.Series(df['c'].values, index=pd.DatetimeIndex(pd.to_datetime(df['T'].values, unit='s', utc=True)).tz_convert(NY))
    return s
btc = closes('BTC')
end = btc.index.max()
tot_days = 0; cnt = {0.5: 0, 1.0: 0, 2.0: 0}; cnt_abs = {1.0: 0}
months = 0
for c, l in ETF.items():
    if c not in d: continue
    s = closes(c)
    s = s[s.index >= pd.Timestamp(l, tz=NY)]
    # часовые свечи помечены временем открытия: закрытие часа 15:00 = значение свечи 15:00
    o = s[(s.index.hour == 14)]  # закрытие 14-15 = цена на 15:00
    e = s[(s.index.hour == 15)]  # закрытие 15-16 = цена на 16:00
    bo = btc.reindex(o.index); be = btc.reindex(e.index)
    o.index = o.index.date; e.index = e.index.date; bo.index = bo.index.date; be.index = be.index.date
    j = pd.concat([o, e, bo, be], axis=1, keys=['o', 'e', 'bo', 'be']).dropna()
    j = j[[pd.Timestamp(x).weekday() < 5 for x in j.index]]
    rel = (j.e / j.o - 1) - (j.be / j.bo - 1)
    tot_days += len(rel)
    for t in cnt: cnt[t] += int((rel >= t / 100).sum())
    cnt_abs[1.0] += int((rel.abs() >= 0.01).sum())
    months = max(months, (end - pd.Timestamp(l, tz=NY)).days / 30.4)
span = (end - pd.Timestamp('2025-10-28', tz=NY)).days / 30.4
print(f"монето-дней (будни, после запуска ETF): {tot_days}; период {span:.1f} мес.")
for t, n in cnt.items():
    print(f"  ход к BTC за 15-16 ET ≥ +{t}%: {n} событий, ≈ {n/span:.1f} в месяц (в среднем по периоду; монет с ETF становилось больше)")
print(f"  |ход к BTC| ≥ 1%: {cnt_abs[1.0]} событий, ≈ {cnt_abs[1.0]/span:.1f} в месяц")
