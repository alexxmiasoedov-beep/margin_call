"""s260–s262 — общее для проверок гипотез s259 на перпах Binance без спота Binance.

- Свечи и фандинг по 19.11.2026 — s224/k_d.pkl и s224/fund_d.pkl (продолжение s2/k2y.pkl и s2/fund2y.pkl, на общем отрезке
  свечи совпадают); переключаются через MC_K и MC_F, как в s117.
- Вселенная — криптоперпы USDT-M (без TradFi, индексов, стейблкоинов и металлов) и «без спота на момент» — как s253 и s259
  (`common259.crypto_perps`, `spot_start`).
- Сделки — `s187/fastbt.trades` (логика `s15/common.trade` без тейка: вход в закрытии 15-мин свечи, стоп по худшей из цены
  стопа и открытия свечи плюс 0,2%, комиссия 0,1% за круг, фактический фандинг); хедж — индекс альтов s103 на фактический
  срок сделки (`fastbt.alt_mv`); плацебо — та же сделка у той же монеты за 45/90/135 сут (`fastbt.placebo`).
- Периоды: А — события 01.10.2024 – 18.10.2026 (данные изучения s259), Б — 19.10 – 19.11.2026 (свежий отрезок после
  изучения: s259 смотрел свечи только по 18.10.2026).
Запуск скриптов — из /home/user/mc_data: python3 -I <repo>/research/s26x/run.py [count|main]."""
import os
import sys

os.environ.setdefault("MC_K", "s224/k_d.pkl")
os.environ.setdefault("MC_F", "s224/fund_d.pkl")
HERE = os.path.dirname(os.path.abspath(__file__))
for _p in ("s187", os.path.join("s259", "study")):
    sys.path.insert(0, os.path.join(HERE, "..", _p))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import fastbt as FB  # noqa: E402
from common259 import crypto_perps, ct, spot_start  # noqa: E402

DAY, BAR = 86400, 900
T0 = int(pd.Timestamp("2024-10-01", tz="UTC").timestamp())
TA = int(pd.Timestamp("2026-10-19", tz="UTC").timestamp())        # конец периода А (данные s259 — по 18.10.2026)
TB = int(pd.Timestamp("2026-11-20", tz="UTC").timestamp())        # конец данных k_d (последняя свеча 19.11 23:45)
MONTH = 30.44 * DAY
K = FB.K


def universe():
    """Криптоперпы: первая и последняя живая свеча (время открытия), дата спота Binance (None — спота не было)."""
    P = crypto_perps(K)
    ss = spot_start(P)
    U = {}
    for p in P:
        nz = np.flatnonzero(K[p]["qv"] > 0)
        if len(nz):
            U[p] = dict(live0=int(K[p]["t"][nz[0]]), live1=int(K[p]["t"][nz[-1]]), spot0=ss[p])
    return U


def nospot_mask(u, te):
    """Свечи (время закрытия te), когда у перпа не было спота Binance и перп торговался не меньше суток."""
    s0 = u["spot0"] if u["spot0"] else np.inf
    return (te < s0) & (te - u["live0"] >= DAY)


def cooldown(te, gap):
    """Оставить события не чаще одного на gap секунд (отсчёт от последнего взятого)."""
    keep, last = [], -10 ** 18
    for k, x in enumerate(te):
        if x - last >= gap:
            keep.append(k); last = x
    return np.array(keep, dtype=np.int64)


def pumps(a):
    """Как s15/kr_panel.pumps: впервые +15% от базы за ≤ 8 свечей, база спокойна (±5% за 2 ч), не чаще раза в сутки."""
    c, h = a["c"].astype(float), a["h"].astype(float)
    n = len(c)
    calm = np.zeros(n, bool)
    calm[8:] = np.abs(c[8:] / c[:-8] - 1) <= 0.05
    hit = np.zeros(n, bool)
    hs = pd.Series(h)
    for L in range(1, 9):
        mx = hs.rolling(L, min_periods=L).max().values
        base = np.r_[np.full(L, np.nan), c[:-L]]
        cb = np.r_[np.zeros(L, bool), calm[:-L]]
        hit |= cb & (mx >= base * 1.15) & (np.arange(n) - L >= 8)
    nz = np.flatnonzero(a["qv"] > 0)
    if not len(nz):
        return np.array([], dtype=np.int64)
    hit &= (np.arange(n) >= nz[0] + 96) & (np.arange(n) <= nz[-1])
    hit &= a["qv"] > 0
    out, last = [], -10 ** 9
    for j in np.flatnonzero(hit):
        if j - last >= 96:
            out.append(int(j)); last = j
    return np.array(out, dtype=np.int64)


def dumps(a):
    """Зеркало pumps (как s259/study/events.dumps): впервые −15% от базы за ≤ 8 свечей, база спокойна, раз в сутки."""
    c, l = a["c"].astype(float), a["l"].astype(float)
    n = len(c)
    calm = np.zeros(n, bool)
    calm[8:] = np.abs(c[8:] / c[:-8] - 1) <= 0.05
    hit = np.zeros(n, bool)
    ls = pd.Series(l)
    for L in range(1, 9):
        mn = ls.rolling(L, min_periods=L).min().values
        base = np.r_[np.full(L, np.nan), c[:-L]]
        cb = np.r_[np.zeros(L, bool), calm[:-L]]
        hit |= cb & (mn <= base * 0.85) & (np.arange(n) - L >= 8)
    nz = np.flatnonzero(a["qv"] > 0)
    if not len(nz):
        return np.array([], dtype=np.int64)
    hit &= (np.arange(n) >= nz[0] + 96) & (np.arange(n) <= nz[-1])
    hit &= a["qv"] > 0
    out, last = [], -10 ** 9
    for j in np.flatnonzero(hit):
        if j - last >= 96:
            out.append(int(j)); last = j
    return np.array(out, dtype=np.int64)


def period(te, hold_h):
    """«А», «Б» или None: событие с полным сроком сделки внутри данных."""
    te = np.asarray(te, np.int64)
    return np.where((te >= T0) & (te < TA), "А", np.where((te >= TA) & (te <= TB - hold_h * 3600), "Б", None))


def trades(E, side, hold_h, sl=0.25):
    """E: DataFrame (s, i, te). Добавляет net, stop, hed (хедж индексом альтов на фактический срок), pl (плацебо)."""
    out = []
    for s, g in E.groupby("s"):
        g = g.copy()
        I = g.i.values.astype(np.int64)
        ok, net, stp, bars, tend = FB.trades(s, I, sl, hold_h, side)
        t = K[s]["t"].astype(np.int64)
        g["net"] = np.where(ok, net, np.nan)
        g["stop"] = np.where(ok, stp, False)
        mv = FB.alt_mv(t[I] + BAR, np.where(ok, tend, t[I] + BAR))
        g["hed"] = g.net.values - side * mv
        g["pl"] = FB.placebo(s, I, sl, hold_h, side)
        out.append(g)
    X = pd.concat(out, ignore_index=True) if out else E.assign(net=np.nan, stop=False, hed=np.nan, pl=np.nan)
    return X[X.net.notna()].reset_index(drop=True)


def line(x, months, mid=None):
    if len(x) < 5:
        return f"n={len(x)}" + (f", среднее {x.net.mean():+.2%}" if len(x) else "")
    m, t, n = ct(x.net, x.te)
    mh, th, _ = ct(x.hed, x.te)
    md, td, _ = ct(x.net - x.pl, x.te)
    s = f"n={n} ({n / months:.1f} в месяц), {m:+.2%} (t по неделям {t:+.1f})"
    if mid is not None:
        s += f"; половины {x[x.te < mid].net.mean():+.2%} / {x[x.te >= mid].net.mean():+.2%}"
    return (s + f"; с хеджем {mh:+.2%} (t {th:+.1f}); сверх плацебо {md:+.2%} (t {td:+.1f}), плацебо у "
            f"{x.pl.notna().mean():.0%}; стопов {x.stop.mean():.0%}")


def verdict(A, B, name):
    """Порог: правило владельца на А (≥ 20 в месяц, t ≥ 3 по неделям, обе половины > 0, сверх плацебо > 0) и знак на Б."""
    mA = (TA - T0) / MONTH
    mid = float(np.median(A.te)) if len(A) else 0
    m, t, n = ct(A.net, A.te) if len(A) >= 5 else (np.nan, np.nan, len(A))
    h1, h2 = A[A.te < mid].net.mean(), A[A.te >= mid].net.mean()
    md = (A.net - A.pl).mean()
    conds = (("≥ 20 в месяц", n / mA >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
             ("сверх плацебо > 0", md > 0), ("Б: среднее > 0", len(B) > 0 and B.net.mean() > 0))
    ok = all(c for _, c in conds)
    print(f"\n{name} — порог: " + "; ".join(f"{k} — {'да' if c else 'нет'}" for k, c in conds)
          + f". ИТОГ: {'пройден' if ok else 'не пройден'}")
    return ok
