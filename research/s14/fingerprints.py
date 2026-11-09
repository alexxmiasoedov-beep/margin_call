"""Отпечатки алгоритмов в ленте сделок монеты: самые частые точные размеры сделок и их свойства.
  - круглость: 1000 или 500 монет — обычная ручная торговля; частый некруглый размер (3517,6) — похоже на робота;
  - часы: робот торгует ровно круглые сутки, люди — по сессиям (Азия, Европа, США);
  - ритм: повторяется ли интервал между сделками одного размера;
  - пары: покупка и продажа одного размера в пределах 5 с — признак самоторговли (рисование объёма) или перекладки;
  - по месяцам: когда размер появился и исчез (смена маркетмейкера или алгоритма).
Второй проход по ленте: поминутный объём каждого из частых размеров (покупки и продажи) → s14/<МОНЕТА>_fp.pkl.

Запуск из папки с данными (после build.py): python3 s14/fingerprints.py GPS ONE"""
import collections
import glob
import os
import pickle
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build import csv_in

TOP = 30                                                  # сколько самых частых размеров разбирать


def sig(q):
    """Значащих цифр в размере: 1000 → 1, 1500 → 2, 1234 → 4, 3517,6 → 5."""
    s = f"{q:.8f}".rstrip("0").rstrip(".")
    return len(s.replace(".", "").lstrip("0")) if "." in s else len(s.lstrip("0").rstrip("0"))


def scan(coin, sizes):
    """Второй проход: сделки выбранных размеров — время, сторона, цена; поминутный объём по каждому размеру."""
    S = np.array(sorted(sizes)); rows = []
    for f in sorted(glob.glob(f"s14raw/{coin}/aggTrades/*.zip")):
        d = csv_in(f, usecols=[1, 2, 5, 6], names=["id", "p", "q", "f", "l", "t", "m"],
                   dtype={"p": "float64", "q": "float64", "t": "int64", "m": "str"})
        d = d[d.q.isin(S)]
        rows.append(pd.DataFrame({"t": d.t.values, "q": d.q.values, "p": d.p.values,
                                  "sell": d.m.str.lower().eq("true").values}))
    return pd.concat(rows, ignore_index=True).sort_values("t", kind="stable")


def report(coin):
    X = pickle.load(open(f"s14/{coin}.pkl", "rb"))
    B = X["bars"]; tot = int(B.n.sum())
    allc = collections.Counter(X["sizes"]["buy"]) + collections.Counter(X["sizes"]["sell"])
    top = [q for q, _ in allc.most_common(TOP)]
    T = scan(coin, top)
    T["hour"] = (T.t // 3600000) % 24; T["month"] = pd.to_datetime(T.t, unit="ms").dt.strftime("%y-%m")
    base_h = B.groupby((B.index // 60) % 24).n.sum(); base_h = base_h / base_h.sum()
    print(f"\n===== {coin}: сделок (aggTrades) {tot:,}, минут {len(B):,}; {TOP} самых частых размеров:")
    print("  размер | значащих цифр | сделок, доля | покупок | равномерность по часам (1 — ровно круглые сутки) | "
          "пар покупка+продажа за 5 с | самый частый интервал между сделками | месяцы активности")
    rows = []
    for q in top:
        x = T[T.q == q]
        n = len(x); hc = x.groupby("hour").size().reindex(range(24), fill_value=0) / max(n, 1)
        flat = 1 - 0.5 * np.abs(hc - 1 / 24).sum()          # 1 — равномерно по 24 часам
        flat_b = 1 - 0.5 * np.abs(base_h.reindex(range(24), fill_value=0) - 1 / 24).sum()
        tt = x.t.values; sd = x.sell.values
        # пара: ближайшая сделка того же размера с другой стороны в пределах 5 с
        bt, st = tt[~sd], tt[sd]
        pair = 0
        if len(bt) and len(st):
            j = np.searchsorted(st, bt); near = np.minimum(np.abs(st[np.clip(j, 0, len(st) - 1)] - bt),
                                                           np.abs(st[np.clip(j - 1, 0, len(st) - 1)] - bt))
            pair = (near <= 5000).sum() * 2 / n
        gaps = np.diff(tt) // 1000
        gaps = gaps[(gaps > 0) & (gaps < 3600)]
        mode_gap, mode_share = (0, 0.0)
        if len(gaps):
            vc = pd.Series(gaps).value_counts(); mode_gap, mode_share = int(vc.index[0]), vc.iloc[0] / len(gaps)
        mon = x.groupby("month").size()
        act = mon[mon >= 0.05 * mon.max()]
        rows.append(dict(q=q, sig=sig(q), n=n, share=n / tot, buy=(~x.sell).mean(), flat=flat, pair=pair,
                         gap=mode_gap, gap_share=mode_share, m0=act.index.min(), m1=act.index.max(), months=len(act)))
        print(f"  {q:>12g} | {sig(q)} | {n:>9,} {n / tot:6.2%} | {(~x.sell).mean():4.0%} | {flat:4.2f} (у всех сделок {flat_b:4.2f}) | "
              f"{pair:4.0%} | {mode_gap} с у {mode_share:4.0%} | {act.index.min()}…{act.index.max()} ({len(act)} мес.)")
    R = pd.DataFrame(rows)
    # поминутный объём каждого размера: покупки (+) и продажи (−), в монетах
    T["min"] = T.t // 60000; T["sq"] = np.where(T.sell, -T.q, T.q)
    flow = T.pivot_table(index="min", columns="q", values="sq", aggfunc="sum", fill_value=0.0)
    cnt = T.pivot_table(index="min", columns="q", values="sq", aggfunc="size", fill_value=0)
    pickle.dump(dict(table=R, flow=flow, count=cnt, trades=T[["t", "q", "p", "sell"]]), open(f"s14/{coin}_fp.pkl", "wb"))
    return R


def gps_ban(R):
    """GPS: самые частые размеры по неделям вокруг отключения маркетмейкера Binance (09.03.2025 = начало недели +0)."""
    Q = pickle.load(open("s14/GPS_fp.pkl", "rb")); T = Q["trades"]
    ban = pd.Timestamp("2025-03-09", tz="UTC").value // 10 ** 6
    T = T.assign(wk=(T.t - ban) // (7 * 86400 * 1000))
    T = T[(T.wk >= -3) & (T.wk <= 6)]
    tab = T.pivot_table(index="q", columns="wk", values="t", aggfunc="size", fill_value=0)
    tab = tab.loc[[q for q in R.q if q in tab.index][:15]]
    tab.columns = [f"{int(w):+d}" for w in tab.columns]
    print("\n===== GPS: сделки самых частых размеров по неделям вокруг отключения маркетмейкера (09.03.2025 — неделя +0):")
    print(tab.to_string())


if __name__ == "__main__":
    for c in sys.argv[1:]:
        R = report(c)
        if c == "GPS":
            gps_ban(R)
