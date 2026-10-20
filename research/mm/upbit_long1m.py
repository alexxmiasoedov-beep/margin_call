"""Лонг от объявления о листинге Upbit (к воне) до открытия торгов, если узнавать об объявлении за минуту.
Объявление = первая минутная свеча фьючерса Binance с ростом ≥ +3% и объёмом ≥ 20× среднего в 4 ч до открытия.
Вход — open следующей минуты +0,3%; выход — open минуты открытия торгов на Upbit; комиссии 0,1%."""
import pickle, datetime
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import bv
UTC = datetime.timezone.utc; MSK = datetime.timezone(datetime.timedelta(hours=3))
f = lambda t: datetime.datetime.fromtimestamp(t, MSK).strftime("%d.%m.%y %H:%M")
day = lambda t: datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d")
rows = pickle.load(open("mm/upbit_short_all.pkl", "rb"))
def load(r):
    days = sorted({day(r["t"] - 6 * 3600), day(r["t"])})
    return r, bv.kfull(r["base"], "klines", "1m", (), days)
with ThreadPoolExecutor(16) as ex: data = list(ex.map(load, rows))
out = []
for r, k in data:
    if k is None: continue
    t, o, c, qv = k[:, 0], k[:, 1], k[:, 4], k[:, 6]
    io = int(np.searchsorted(t, r["t"] // 60 * 60))
    if io >= len(t) or io < 300: continue
    base = qv[io - 300:io - 240].mean() + 1e-9
    spike = [j for j in range(io - 240, io) if c[j] / o[j] - 1 >= 0.03 and qv[j] >= 20 * base]
    if not spike:
        out.append(dict(base=r["base"], t=r["t"], ann=None)); continue
    j = spike[0]; entry = o[j + 1] * 1.003; exit_ = o[io]
    out.append(dict(base=r["base"], t=r["t"], ann=t[j], lead=(r["t"] - t[j]) / 60, jump=c[j] / o[j] - 1,
                    long=exit_ / entry - 1 - 0.001, ideal=exit_ / o[j] - 1, short48=r["48 ч"][0]))
pickle.dump(out, open("mm/upbit_long1m.pkl", "wb"))
w = [x for x in out if x["ann"]]
print(f"листингов с минутными данными: {len(out)}; с явной реакцией на объявление (скачок ≥ +3% за минуту): {len(w)}")
L = np.array([x["long"] for x in w]); I = np.array([x["ideal"] for x in w])
print(f"лонг с минутной задержкой до открытия торгов: {L.mean()*100:+.1f}% на сделку, медиана {np.median(L)*100:+.1f}%, в плюсе {np.mean(L > 0)*100:.0f}% "
      f"| если войти в саму минуту объявления: {I.mean()*100:+.1f}% | объявление за {np.median([x['lead'] for x in w]):.0f} мин до открытия (медиана)")
for nm, a, b in (("2025", 0, datetime.datetime(2026, 1, 1, tzinfo=UTC).timestamp()), ("2026", datetime.datetime(2026, 1, 1, tzinfo=UTC).timestamp(), 9e12)):
    x = np.array([v["long"] for v in w if a <= v["t"] < b]); print(f"  {nm}: n={len(x)}, {x.mean()*100:+.1f}% на сделку, медиана {np.median(x)*100:+.1f}%, в плюсе {np.mean(x > 0)*100:.0f}%")
both = np.array([x["long"] + x["short48"] for x in w])
print(f"лонг до открытия + шорт от открытия на 48 ч: {both.mean()*100:+.1f}% на пару сделок, в плюсе {np.mean(both > 0)*100:.0f}%")
for x in sorted(w, key=lambda x: x["t"])[-12:]:
    print(f"  {x['base']:8s} объявление {f(x['ann'])} (скачок {x['jump']*100:+.0f}%), открытие {f(x['t'])}: лонг {x['long']*100:+5.1f}%, шорт 48 ч {x['short48']*100:+5.1f}%")
