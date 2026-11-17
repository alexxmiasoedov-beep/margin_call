"""s100 — стоимость исполнения: проскальзывание рыночного входа в шорт (продажа в заявки покупателей) по снимкам стакана
фьючерсов Binance (data.binance.vision, bookDepth: каждые ~30 с накопленный объём в $ на ±0,2/1/2/3/4/5% от середины).
Выборка — до 60 случайных сделок каждого журнала (сделки бэктеста, как в s96). Проскальзывание — средняя цена продажи
суммы N против середины: накопленный объём между уровнями считается равномерным. Запуск из папки с данными:
python3 <путь>/s100/slip.py"""
import datetime as dt
import io
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s96"))
from portfolio import load  # noqa: E402

URL = "https://data.binance.vision/data/futures/um/daily/bookDepth/{s}USDT/{s}USDT-bookDepth-{d}.zip"
SIZES = (100, 500, 1000, 5000, 20000)
PER_J = 60


def fetch(s, d):
    for i in range(4):
        try:
            b = urllib.request.urlopen(urllib.request.Request(URL.format(s=s, d=d), headers={"User-Agent": "research"}), timeout=60).read()
            z = zipfile.ZipFile(io.BytesIO(b))
            x = pd.read_csv(z.open(z.namelist()[0]))
            x["ts"] = (pd.to_datetime(x.timestamp) - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s")
            return x[x.percentage < 0]                               # сторона покупателей — в неё продаёт шорт
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except Exception:
            pass
        time.sleep(3 * (i + 1))
    return None


def slippage(snap, n):
    """Средняя цена продажи суммы n против середины, доля; None — объёма в 5% не хватает."""
    p = np.r_[0.0, -snap.percentage.values[::-1] / 100]            # 0, 0,2%, 1%, 2%, … по возрастанию
    q = np.r_[0.0, snap.notional.values[::-1]]
    if q[-1] < n:
        return None
    cost, got = 0.0, 0.0
    for k in range(1, len(p)):
        take = min(q[k] - q[k - 1], n - got)
        if take <= 0:
            break
        frac = take / (q[k] - q[k - 1]) if q[k] > q[k - 1] else 1.0
        cost += take * (p[k - 1] + (p[k] - p[k - 1]) * frac / 2)    # равномерно внутри полосы: средняя точка взятой части
        got += take
    return cost / n


def one(row):
    s, t = row.s, int(row.t)
    d = dt.datetime.fromtimestamp(t - 1, dt.timezone.utc).strftime("%Y-%m-%d")
    x = fetch(s, d)
    if x is None or x.empty:
        return None
    before = x[x.ts <= t]
    if before.empty:
        return None
    last = before.ts.max()
    snap = before[before.ts == last].sort_values("percentage", ascending=False)   # −0,2, −1, … −5
    if t - last > 600:
        return None
    out = {"j": row.j, "s": s, "t": t, "r": row.r, "bid02": float(snap.notional.iloc[0])}
    for n in SIZES:
        out[f"slip_{n}"] = slippage(snap, n)
    return out


def main():
    X = load()
    S = pd.concat([g.sample(min(PER_J, len(g)), random_state=1) for _, g in X.groupby("j")])
    with ThreadPoolExecutor(8) as ex:
        R = [r for r in ex.map(one, S.itertuples(index=False)) if r]
    D = pd.DataFrame(R); D.to_pickle("s100/slip.pkl")
    print(f"Сделок в выборке {len(S)}, со снимком стакана не старше 10 мин до входа: {len(D)}")
    print("Объём покупателей в 0,2% от середины на входе ($): медиана по журналам")
    print(D.groupby("j").bid02.median().round(0).to_string())
    print("\nПроскальзывание продажи суммы N (медиана по сделкам, % от цены; «—» — не хватает объёма в 5%):")
    rows = []
    for j, g in D.groupby("j"):
        r = {"журнал": j, "сделок": len(g), "доход на сделку": f"{g.r.mean():+.2%}"}
        for n in SIZES:
            v = g[f"slip_{n}"]
            r[f"{n}$"] = f"{v.median():.3%}" if v.notna().mean() >= 0.5 else "—"
        rows.append(r)
    print(pd.DataFrame(rows).to_string(index=False))
    allv = {n: D[f"slip_{n}"] for n in SIZES}
    print("\nВсе журналы: медиана " + ", ".join(f"{n}$ {v.median():.3%} (90%: {v.quantile(.9):.3%}; не хватает объёма {v.isna().mean():.0%})"
                                               for n, v in allv.items()))


if __name__ == "__main__":
    main()
