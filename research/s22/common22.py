"""Общее для проверок гипотез s22 (займы MarginData, ставки маржи, OI, объявления Binance).
Запуск скриптов — из папки с данными (mc_data): python3 /путь/research/s22/<скрипт>.py"""
import datetime
import io
import os
import pickle
import re
import sys
import urllib.error
import urllib.request
import zipfile
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15")); sys.path.insert(0, os.path.join(HERE, "..", "s21"))
from common import BAR, FEE, K, funding, fut_of, live, trade          # noqa: E402

H, DAY = 3600, 86400
UTC = datetime.timezone.utc
CUT = 1764547200                                                    # 01.12.2025 — граница половин, как в s9 и s21
PREF = re.compile(r"^(1000000|100000|10000|1000)")
STABLE = {"DAI", "USDC", "FDUSD", "TUSD", "USDP", "BUSD"}
HSET = (24, 72, 168, 336, 720)                                      # горизонты профиля, ч
G = pickle.load(open("s7/margin.pkl", "rb"))["G"]                   # архив MarginData: [t, bor, rep, br, rank]
COIN_OF = {}                                                         # фьючерс → монета канала (для ставок маржи)
for _c in G:
    _s, _ = fut_of(_c)
    if _s:
        COIN_OF.setdefault(_s, _c)


# ---------------------------------------------------------------- сетка закрытий часов и рынок
def grid():
    """Часовые закрытия всех фьючерсов (только свечи с объёмом) и медиана доходности рынка на горизонтах HSET.
    Кэш s22/grid.pkl."""
    path = "s22/grid.pkl"
    if os.path.exists(path):
        return pickle.load(open(path, "rb"))
    os.makedirs("s22", exist_ok=True)
    t0 = min(int(a["t"][0]) for a in K.values()); t1 = max(int(a["t"][-1]) for a in K.values())
    gr = np.arange((t0 // H + 1) * H, t1, H)
    syms = list(K); C = np.full((len(syms), len(gr)), np.nan, dtype=np.float32)
    for n, s in enumerate(syms):
        a = K[s]; t = a["t"].astype(np.int64) + BAR
        i = np.searchsorted(gr, t)
        ok = (i < len(gr)) & (gr[np.minimum(i, len(gr) - 1)] == t) & (a["qv"] > 0)
        C[n, i[ok]] = a["c"][ok]
    MK = {}
    for h in HSET + (48,):
        r = C[:, h:] / C[:, :-h] - 1
        MK[h] = np.r_[np.nanmedian(r, axis=0), np.full(h, np.nan)].astype(np.float32)
    out = dict(grid=gr, syms=syms, row={s: n for n, s in enumerate(syms)}, C=C, MK=MK)
    pickle.dump(out, open(path, "wb"))
    return out


GR = grid()


def fwd(s, T, h, delay=0, net=False):
    """Шорт фьючерса s от закрытия часа T + delay ч на h ч: доход к рынку (цена + медиана рынка, лонг); net — цена с фандингом
    и комиссией, без рынка. NaN, если свечей нет."""
    g = GR["grid"]; k = int(np.searchsorted(g, T + delay * H))
    if k >= len(g) or g[k] != T + delay * H or k + h >= len(g):
        return np.nan
    c = GR["C"][GR["row"][s]]; c0, c1 = c[k], c[k + h]
    if not (np.isfinite(c0) and np.isfinite(c1)):
        return np.nan
    px = 1 - float(c1) / float(c0)
    if net:
        fr = funding(s)
        f = float(fr[(fr[:, 0] > g[k]) & (fr[:, 0] <= g[k + h]), 1].sum()) if len(fr) else 0.0
        return px + f - FEE
    m = GR["MK"][h][k]
    return px + float(m) if np.isfinite(m) else np.nan


# ---------------------------------------------------------------- ставки маржи (s11/rates, публичная история Binance)
_rates = {}


def rates(coin):
    """Ступенчатая история дневной ставки займа: (времена изменений, ставки) или None."""
    if coin not in _rates:
        p = f"s11/rates/{coin}.csv"
        if os.path.exists(p):
            a = np.loadtxt(p, delimiter=",", ndmin=2)
            a = a[np.argsort(a[:, 0])] if len(a) else a
            _rates[coin] = (a[:, 0], a[:, 1]) if len(a) else None
        else:
            _rates[coin] = None
    return _rates[coin]


def rate_jump(coin, T, lo_d=7, hi_d=0):
    """Ставка в момент T к медиане почасовых значений за [T − lo_d сут, T − hi_d сут). NaN, если истории мало."""
    r = rates(coin)
    if r is None:
        return np.nan
    t, v = r
    i = np.searchsorted(t, T, "right") - 1
    if i < 0:
        return np.nan
    hours = np.arange(T - lo_d * DAY, T - hi_d * DAY, H)
    j = np.searchsorted(t, hours, "right") - 1
    if (j < 0).mean() > 0.2:
        return np.nan
    med = np.median(v[j[j >= 0]])
    return v[i] / med if med > 0 else np.nan


# ---------------------------------------------------------------- OI (5-мин метрики data.binance.vision, кэш s20/metrics)
def metrics_day(sym, day):
    path = f"s20/metrics/{sym}/{day}.npy"
    if os.path.exists(path):
        return np.load(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    url = f"https://data.binance.vision/data/futures/um/daily/metrics/{sym}USDT/{sym}USDT-metrics-{day}.zip"
    arr = np.zeros((0, 3))
    for _ in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
            rows = []
            for ln in z.read(z.namelist()[0]).decode().splitlines()[1:]:
                p = ln.split(",")
                if len(p) >= 4 and p[2] and p[3]:
                    t = datetime.datetime.strptime(p[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp()
                    rows.append((t, float(p[2]), float(p[3])))
            arr = np.array(rows) if rows else arr
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                break
        except Exception:
            pass
    else:
        return arr                                                   # сбой сети — не кэшируем, повторим в другой раз
    np.save(path, arr)
    return arr


def oi_at(sym, T):
    """OI в монетах на момент T (последняя 5-мин отметка не позже T и не старше 15 мин) или NaN."""
    a = metrics_day(sym, datetime.datetime.fromtimestamp(T - 1, UTC).strftime("%Y-%m-%d"))
    if not len(a):
        return np.nan
    i = np.searchsorted(a[:, 0], T, "right") - 1
    return float(a[i, 1]) if i >= 0 and T - a[i, 0] <= 900 else np.nan


# ---------------------------------------------------------------- статистика
def thin(d, gap=DAY, key="s"):
    keep, last = [], {}
    for i, (s, T) in enumerate(zip(d[key].values, d["T"].values)):
        if T - last.get(s, -1e18) >= gap:
            keep.append(i); last[s] = T
    return d.iloc[keep]


def ct(x, T):
    """Среднее и t с кластеризацией по дню входа (среднее по дню, затем t по дням)."""
    d = pd.Series(np.asarray(x, float), index=pd.to_datetime(np.asarray(T), unit="s").date).dropna()
    if len(d) < 10:
        return np.nan, np.nan, len(d)
    g = d.groupby(level=0).mean()
    return d.mean(), g.mean() / g.std() * np.sqrt(len(g)) if len(g) > 2 and g.std() > 0 else np.nan, len(d)


def summ(x, T, pct=True):
    """Строка: n, среднее, t по дням, половины."""
    x = np.asarray(x, float); T = np.asarray(T, float); ok = np.isfinite(x)
    m, t, n = ct(x[ok], T[ok])
    if not n or n < 10:
        return f"n={n} — мало"
    h1, h2 = x[ok & (T < CUT)], x[ok & (T >= CUT)]
    f = 100 if pct else 1
    return (f"n={n:5d} {m * f:+6.2f}% (t {t:+4.1f}; половины {np.nanmean(h1) * f:+.2f}/{np.nanmean(h2) * f:+.2f}%, "
            f"в плюсе {(x[ok] > 0).mean():.0%})")
