"""Флаги Upbit как сигнал (первый взгляд): что было с фьючерсом Binance после появления флага. Данные — выгрузка
tools/upbit_flags.py с сервера (s17/flags_2026-11-03_10.txt, 03.11–10.11.2026: журнал службы хранит около недели).
Цены — 15-мин свечи фьючерсов из архива data.binance.vision (дневные файлы до вчерашнего дня, кэш s17/k/).

Для каждого появления флага (+) у монеты с фьючерсом: вход в закрытии 15-мин свечи, в которой бот увидел флаг; доходность
шорта (только цена) через 4, 24 и 48 ч; «к рынку» — минус медиана шорта остальных монет выгрузки за то же окно.
Запуск из папки с данными: python3 s17/flags_study.py <файл выгрузки>"""
import datetime
import io
import os
import sys
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd

UTC = datetime.timezone.utc
DAYS = []                                                    # дни свечей: от первого флага до последнего + 3 суток, не позже вчера
NAME = {"W": "предупреждение", "P": "скачки цены", "V": "всплеск объёма", "D": "всплеск депозитов",
        "G": "разница с мировой ценой", "C": "концентрация мелких счетов"}


def parse(path):
    rows = []
    for ln in open(path, encoding="utf-8"):
        p = ln.split()
        if len(p) < 7 or not p[0].isdigit():
            continue
        y, md = (2000 + int(p[0][:2]), p[0][2:]) if len(p[0]) == 6 else (2026, p[0])     # v2: ГГММДД, v1: ММДД
        t = datetime.datetime(y, int(md[:2]), int(md[2:]), int(p[1][:2]), int(p[1][2:]), tzinfo=UTC).timestamp()
        rows.append(dict(t=t, sign=p[2], flag=p[3], coin=p[4], fut=None if p[5] == "-" else p[5]))
    return pd.DataFrame(rows)


def day_klines(sym, day):
    path = f"s17/k/{sym}-{day}.npy"
    if os.path.exists(path):
        return np.load(path)
    os.makedirs("s17/k", exist_ok=True)
    url = f"https://data.binance.vision/data/futures/um/daily/klines/{sym}USDT/15m/{sym}USDT-15m-{day}.zip"
    arr = np.zeros((0, 2))
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            z = zipfile.ZipFile(io.BytesIO(r.read()))
        rows = [ln.split(",") for ln in z.read(z.namelist()[0]).decode().splitlines() if ln and ln[0].isdigit()]
        arr = np.array([(int(x[0]) // 1000, float(x[4])) for x in rows])
    except Exception:
        pass
    np.save(path, arr)
    return arr


def series(sym):
    a = [day_klines(sym, d) for d in DAYS]
    a = [x for x in a if len(x)]
    return pd.Series(np.concatenate(a)[:, 1], index=np.concatenate(a)[:, 0].astype(np.int64)) if a else None


if __name__ == "__main__":
    F = parse(sys.argv[1] if len(sys.argv) > 1 else "s17/flags_2026-11-03_10.txt")
    last = (datetime.datetime.now(UTC) - datetime.timedelta(days=1)).date()
    d, end = datetime.datetime.fromtimestamp(F.t.min(), UTC).date() - datetime.timedelta(days=1), \
        min(datetime.datetime.fromtimestamp(F.t.max(), UTC).date() + datetime.timedelta(days=3), last)
    while d <= end:
        DAYS.append(d.isoformat()); d += datetime.timedelta(days=1)
    syms = sorted(set(F.fut.dropna()) | {"BTC"})
    with ThreadPoolExecutor(8) as pool:
        S = dict(zip(syms, pool.map(series, syms)))
    S = {s: v for s, v in S.items() if v is not None and len(v)}
    print(f"флагов в выгрузке {len(F)}, появлений {int((F.sign == '+').sum())}, монет с фьючерсом {len(S) - 1}; "
          f"цены: {pd.to_datetime(min(v.index[0] for v in S.values()), unit='s'):%d.%m} – "
          f"{pd.to_datetime(max(v.index[-1] for v in S.values()) + 900, unit='s'):%d.%m %H:%M} UTC")

    def ret(sym, t0, h):
        v = S.get(sym)
        if v is None:
            return np.nan
        b0 = (int(t0) // 900) * 900                         # свеча, в которой бот увидел флаг; вход — её закрытие
        b1 = b0 + h * 3600
        if b0 not in v.index or b1 not in v.index:
            return np.nan
        return 1 - v[b1] / v[b0]

    rows = []
    for e in F[(F.sign == "+") & F.fut.notna()].itertuples():
        r = dict(t=e.t, flag=e.flag, coin=e.coin, fut=e.fut)
        for h in (4, 24, 48):
            x = ret(e.fut, e.t, h)
            others = [ret(s, e.t, h) for s in S if s not in (e.fut, "BTC")]
            r[f"s{h}"] = x
            r[f"m{h}"] = x - np.nanmedian(others) if np.isfinite(x) and np.isfinite(others).any() else np.nan
        rows.append(r)
    R = pd.DataFrame(rows)
    both = R[R.flag.isin(["V", "D"])].groupby(["t", "fut"]).flag.nunique()
    R["vd"] = [both.get((t, f), 0) == 2 for t, f in zip(R.t, R.fut)]
    print("\nшорт после появления флага (только цена, без комиссии); «к рынку» — минус медиана шорта остальных монет:")
    for nm, m in [(f"{k} {NAME[k]}", R.flag == k) for k in "PVDGC"] + [("V и D вместе", (R.flag == "D") & R.vd)]:
        g = R[m]
        if not len(g):
            continue
        parts = []
        for h in (4, 24, 48):
            x, y = g[f"s{h}"].dropna(), g[f"m{h}"].dropna()
            if len(x):
                parts.append(f"{h} ч: n={len(x)}, {x.mean() * 100:+.1f}% (медиана {x.median() * 100:+.1f}%, в плюсе {(x > 0).mean():.0%}), "
                             f"к рынку {y.mean() * 100:+.1f}%")
        print(f"  {nm:30s} " + " | ".join(parts))
    R.to_pickle("s17/flags_returns.pkl")
