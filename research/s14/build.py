"""Разбор ленты сделок (aggTrades) одной монеты из s14raw/<МОНЕТА>/aggTrades — за один проход по каждому месяцу:
  - минутные свечи: число сделок, покупки и продажи по рынку (штук и $), открытие/максимум/минимум/закрытие;
  - сколько раз встречался каждый точный размер сделки, отдельно у покупок и продаж по рынку (для поиска «отпечатков»).
Плюс открытый интерес и соотношения лонгов/шортов (metrics, 5 мин), толщина стакана ±1…5% (bookDepth, 30 с → 1 мин),
фандинг и премия к индексу. Результат — s14/<МОНЕТА>.pkl.

Запуск из папки с данными: python3 s14/build.py GPS ONE"""
import collections
import glob
import io
import os
import pickle
import sys
import time
import zipfile
import numpy as np, pandas as pd


def csv_in(path, **kw):
    """CSV из zip-архива; в старых файлах Binance нет строки заголовка, в новых есть — её пропускаем."""
    with zipfile.ZipFile(path) as z:
        raw = z.read(z.namelist()[0])
    head = raw[:1].isdigit()
    return pd.read_csv(io.BytesIO(raw), header=None, skiprows=0 if head else 1, **kw)


def trades(coin):
    bars, sizes = [], {"buy": collections.Counter(), "sell": collections.Counter()}
    for f in sorted(glob.glob(f"s14raw/{coin}/aggTrades/*.zip")):
        t0 = time.time()
        # agg_trade_id, price, quantity, first_trade_id, last_trade_id, transact_time, is_buyer_maker
        d = csv_in(f, usecols=[1, 2, 3, 4, 5, 6], names=["id", "p", "q", "f", "l", "t", "m"],
                   dtype={"p": "float64", "q": "float64", "f": "int64", "l": "int64", "t": "int64", "m": "str"})
        d["sell"] = d.m.str.lower().eq("true")             # покупатель — мейкер, значит по рынку продавали
        d["v"] = d.p * d.q
        d["n"] = d.l - d.f + 1
        d["min"] = d.t // 60000
        g = d.groupby("min", sort=True)
        b = pd.DataFrame({"o": g.p.first(), "h": g.p.max(), "l": g.p.min(), "c": g.p.last(), "n": g.size(), "fills": g.n.sum()})
        for side, mask in (("buy", ~d.sell), ("sell", d.sell)):
            s = d[mask].groupby("min")
            b[f"{side}_q"] = s.q.sum(); b[f"{side}_v"] = s.v.sum(); b[f"{side}_n"] = s.size()
            vc = d.q[mask].value_counts()
            sizes[side].update(vc[vc >= 3].to_dict())                # размер, встреченный 1–2 раза за месяц, отпечатком не бывает
        bars.append(b.fillna(0))
        print(f"  {os.path.basename(f)}: сделок {len(d):,}, минут {len(b):,}, {time.time() - t0:.0f} с", flush=True)
    B = pd.concat(bars); B = B[~B.index.duplicated()].sort_index()
    return B, sizes


def secs(col):
    """Время «2025-03-01 00:00:08» → секунды Unix (pandas 3 сам выбирает единицы datetime64, поэтому приводим явно)."""
    return pd.to_datetime(col).values.astype("datetime64[s]").astype("int64")


def daily(coin, kind, **kw):
    fs = sorted(glob.glob(f"s14raw/{coin}/{kind}/*.zip"))
    return pd.concat([csv_in(f, **kw) for f in fs], ignore_index=True) if fs else pd.DataFrame()


def build(coin):
    B, sizes = trades(coin)
    M = daily(coin, "metrics", names=["time", "sym", "oi", "oi_usd", "top_acc", "top_pos", "all_acc", "taker_ratio"],
              usecols=[0, 2, 3, 4, 5, 6, 7])
    if len(M):
        M["time"] = secs(M.time)
        M = M.drop_duplicates("time").set_index("time").sort_index()
    D = daily(coin, "bookDepth", names=["time", "pct", "depth", "usd"])
    if len(D):
        D["time"] = secs(D.time) // 60 * 60                                           # снимки раз в 30 с → минута
        D = D.pivot_table(index="time", columns="pct", values="usd", aggfunc="mean").sort_index()
        D.columns = [f"d{int(c):+d}" for c in D.columns]
    F = daily(coin, "fundingRate", names=["time", "iv", "rate"])                      # calc_time, интервал, ставка
    if len(F):
        F = F.assign(time=F.time // 1000).drop_duplicates("time").set_index("time").sort_index()
    P = daily(coin, "premiumIndexKlines", names=["time", "o", "h", "l", "c"], usecols=[0, 1, 2, 3, 4])
    if len(P):
        P = P.assign(time=P.time // 1000).drop_duplicates("time").set_index("time").sort_index()
    out = dict(bars=B, sizes={k: dict(v) for k, v in sizes.items()}, metrics=M, depth=D, funding=F, premium=P)
    with open(f"s14/{coin}.pkl", "wb") as f:
        pickle.dump(out, f)
    print(f"{coin}: минут {len(B):,} ({pd.to_datetime(B.index[0] * 60, unit='s'):%d.%m.%Y} – "
          f"{pd.to_datetime(B.index[-1] * 60, unit='s'):%d.%m.%Y}), размеров сделок {len(sizes['buy']) + len(sizes['sell']):,}; "
          f"metrics {len(M):,} строк, стакан {len(D):,} минут, фандинг {len(F)}, премия {len(P)}", flush=True)


if __name__ == "__main__":
    for c in sys.argv[1:]:
        build(c)
