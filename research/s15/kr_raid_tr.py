"""Пересечение «корейского набега» с журналом 🇹🇷: для каждого сигнала набега (доля Кореи ≥ 20% и ×3, рост ≥ 10% за 4 ч) —
доля пары XXX/TRY спота Binance в обороте за час (вместе с фьючерсом) и её обычный уровень (медиана часовых долей за 7 суток)
на закрытиях часов T−4 ч … T. Если хоть раз доля ≥ 10% и ×3 — 🇹🇷 сработал бы на том же движении.
15-мин свечи спота XXXTRY и USDTTRY — из архива data.binance.vision (кэш s15/try/). Запуск: python3 s15/kr_raid_tr.py"""
import io
import os
import sys
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import K
from kr_raid import kr_signals, overlap, with_trades, line, P
from kr_raid2 import select, EX


def month_klines(pair, ym):
    path = f"s15/try/{pair}-{ym}.npy"
    if os.path.exists(path):
        return np.load(path)
    os.makedirs("s15/try", exist_ok=True)
    url = f"https://data.binance.vision/data/spot/monthly/klines/{pair}/15m/{pair}-15m-{ym}.zip"
    arr = np.zeros((0, 3))
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            z = zipfile.ZipFile(io.BytesIO(r.read()))
        rows = [ln.split(",") for ln in z.read(z.namelist()[0]).decode().splitlines() if ln and ln[0].isdigit()]
        ts = np.array([int(x[0]) for x in rows], dtype=np.int64)
        ts = np.where(ts > 1e14, ts // 1000, ts) // 1000                # в архиве 2025+ время в микросекундах
        arr = np.c_[ts, np.array([float(x[4]) for x in rows]), np.array([float(x[7]) for x in rows])]
    except Exception:
        pass
    np.save(path, arr)
    return arr


def series(pair, months):
    a = [month_klines(pair, m) for m in months]
    a = [x for x in a if len(x)]
    if not a:
        return None
    a = np.concatenate(a)
    return pd.DataFrame(a[:, 1:], index=a[:, 0].astype(np.int64), columns=["c", "qv"]).sort_index()


def tr_hit(s, T):
    base = s[4:] if s.startswith("1000") and not s.startswith("1000000") else (s[7:] if s.startswith("1000000") else s)
    months = sorted({pd.to_datetime(x, unit="s").strftime("%Y-%m") for x in (T - 8 * 86400, T)})
    tr = series(f"{base}TRY", months)
    if tr is None:
        return None                                              # пары к лире нет
    fx = series("USDTTRY", months)
    a = K[s]; t = a["t"]
    fut = pd.Series(a["qv"].astype(float), index=t)
    hours = np.arange(T - 8 * 86400, T + 1, 3600)
    def share(h):
        idx = [h - 900 * k for k in range(1, 5)]
        trv = sum(float(tr.qv.get(i, 0.0)) / float(fx.c.get(i, np.nan) or np.nan) for i in idx if i in tr.index and i in fx.index)
        fv = sum(float(fut.get(i, 0.0)) for i in idx)
        return trv / (trv + fv) if trv + fv > 0 else np.nan
    sh = pd.Series([share(h) for h in hours], index=hours)
    hit = False
    for h in range(T - 4 * 3600, T + 1, 3600):
        norm = sh[(sh.index < h) & (sh.index >= h - 7 * 86400)].median()
        if sh.get(h, np.nan) >= 0.10 and sh.get(h, np.nan) >= 3 * norm:
            hit = True
    return hit


if __name__ == "__main__":
    cut = float(np.median(np.concatenate([d["T"].values for d in P.values()])))
    S20 = kr_signals(); S20 = S20[S20.share >= 0.20]
    E = select(lambda d: (d.r4 >= 0.10) & (d.share >= 0.20) & (d.share >= 3 * d.norm)); E = E[~overlap(E, S20)]
    with ThreadPoolExecutor(8) as pool:
        E["tr"] = list(pool.map(lambda x: tr_hit(x[0], x[1]), zip(E.s, E["T"])))
    r = with_trades(E, **EX)
    print(f"сигналов набега {len(r)}: пары к лире нет — {r.tr.isna().sum()}, есть, но 🇹🇷 не сработал бы — {(r.tr == False).sum()}, "
          f"🇹🇷 сработал бы — {(r.tr == True).sum()}")
    for nm, m in (("пары к лире нет", r.tr.isna()), ("пара есть, 🇹🇷 молчит", r.tr == False), ("🇹🇷 сработал бы", r.tr == True),
                  ("без пересечения с 🇹🇷 (нет пары или молчит)", r.tr != True)):
        print(f"  {nm:44s} {line(r[m.values], cut)}")
