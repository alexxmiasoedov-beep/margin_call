"""s43 — проверка оповещений oi_detector (гипотезы — ВЫВОДЫ.md, записаны до разбора постов). Посты — s43/rows.pkl
(oi_parse.py). Группы: цвет поста (🟢 OI вырос / 🔴 упал за 15 мин) × знак изменения цены за 1 ч. Событие — первый пост
монеты в группе после ≥ 24 ч без такого. Сделки (s15/common.trade) — с закрытия первой 15-мин свечи после поста:
S_7_20 — шорт, тейк 7%, стоп 20%, 48 ч; S_10_15 — тейк 10%, стоп 15%, 24 ч; S_7d — 7 сут, стоп +50%. Плацебо — та же
монета за 45/90/135 сут. Доход к рынку — по часовой сетке s22 с первого часа после входа. Половины — до и после
01.12.2025, t по дням. Итог — s43/events.pkl, s43/jr.pkl. Запуск из папки с данными."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15"))
from common import K, fut_of, live, trade  # noqa: E402

DAY = 86400
CUT = pd.Timestamp(os.environ.get("MC_CUT", "2025-12-01"), tz="UTC").timestamp()     # MC_CUT — середина другой выборки
PL = (45, 90, 135)
EXITS = {"S_7_20": dict(tp=0.07, sl=0.20, hold_h=48), "S_10_15": dict(tp=0.10, sl=0.15, hold_h=24),
         "S_7d": dict(tp=None, sl=0.50, hold_h=168)}
GROUPS = {"up_up": "🟢 OI ↑, цена ↑ (новые лонги на росте)", "up_dn": "🟢 OI ↑, цена ↓ (новые шорты на падении)",
          "dn_up": "🔴 OI ↓, цена ↑ (закрытие шортов на росте)", "dn_dn": "🔴 OI ↓, цена ↓ (закрытие лонгов на падении)"}
HZ = (4, 24, 72)
GR = pickle.load(open("s22/grid.pkl", "rb"))
_mk = {}


def mk(h):
    if h not in _mk:
        C = GR["C"]
        r = C[:, h:] / C[:, :-h] - 1
        _mk[h] = np.r_[np.nanmedian(r, axis=0), np.full(h, np.nan)]
    return _mk[h]


def idx_at(s, ts):
    """Последняя закрытая 15-мин свеча к моменту ts."""
    t = K[s]["t"]; i = int(np.searchsorted(t, ts - 900, "right")) - 1
    return i if i >= 96 else None


def deal(s, i, ex):
    r = trade(s, i + 1, side=-1, **EXITS[ex])
    return r["net"] if r else None


def rel(s, te, h):
    """Доход монеты к рынку (медиана фьючерсов) за h часов с первого часа сетки после te; знак — в сторону шорта."""
    gr = GR["grid"]; k = int(np.searchsorted(gr, te))
    row = GR["row"].get(s)
    if row is None or k + h >= len(gr):
        return np.nan
    c0, c1 = GR["C"][row, k], GR["C"][row, k + h]
    if not (c0 > 0 and c1 > 0):
        return np.nan
    return -((c1 / c0 - 1) - mk(h)[k])


def cl_t(y, x, g):
    """МНК y = a + b·x с кластерами g: b и t (поправка G/(G−1))."""
    y, x, g = np.asarray(y, float), np.asarray(x, float), np.asarray(g)
    m = ~np.isnan(y)
    y, x, g = y[m], x[m], g[m]
    X = np.c_[np.ones_like(x), x]
    XtXi = np.linalg.pinv(X.T @ X)
    b = XtXi @ X.T @ y
    u = y - X @ b
    S = pd.DataFrame(X * u[:, None]).groupby(g).sum().values
    G = len(S)
    if G < 5:
        return b[1], np.nan
    V = XtXi @ (S.T @ S) @ XtXi * G / (G - 1)
    return b[1], b[1] / np.sqrt(V[1, 1]) if V[1, 1] > 0 else np.nan


def ct(x, T):
    """Среднее по сделкам и его t с кластерами по дням входа."""
    y = np.asarray(x, float); g = (np.asarray(T, float) // DAY).astype(np.int64)
    m = ~np.isnan(y); y, g = y[m], g[m]
    if len(y) < 5:
        return np.nan, np.nan, len(y)
    u = pd.Series(y - y.mean()).groupby(g).sum().values
    G = len(u)
    se = np.sqrt((u ** 2).sum() * G / (G - 1)) / len(y) if G > 1 else np.nan
    return y.mean(), y.mean() / se if se and se > 0 else np.nan, len(y)


def sym_of(r):
    s = fut_of(r.coin)[0]
    if s is None and isinstance(r.tick, str) and r.tick:
        s = fut_of(r.tick)[0]
    return s


def events(R):
    rows = []
    R = R[(R.dir != 0) & (R.p1h != 0)].copy()
    R["g"] = np.where(R.dir > 0, "up_", "dn_") + np.where(R.p1h > 0, "up", "dn")
    R["s"] = [sym_of(r) for r in R.itertuples()]
    R = R[R.s.notna()]
    for (s, g), x in R.groupby(["s", "g"]):
        lo, hi = live(s)
        prev = -np.inf
        for r in x.sort_values("t").itertuples():
            new_ev = r.t - prev >= DAY
            prev = r.t
            if not new_ev or r.t - 3 * DAY < lo or r.t > hi:
                continue
            i = idx_at(s, r.t)
            if i is None:
                continue
            te = float(K[s]["t"][i + 1]) + 900 if i + 1 < len(K[s]["t"]) else np.nan
            row = dict(s=s, g=g, t=r.t, score=r.score, fire=r.fire, sig=r.sig, oi5m=r.oi5m, oi15m=r.oi15m, oi1h=r.oi1h,
                       oi24h=r.oi24h, p5m=r.p5m, p15m=r.p15m, p1h=r.p1h, p24h=r.p24h, fund=r.fund, vol24=r.vol24,
                       ls5=getattr(r, "ls5", np.nan), ls1h=getattr(r, "ls1h", np.nan), rsi15=getattr(r, "rsi15", np.nan),
                       rsi1h=getattr(r, "rsi1h", np.nan))
            for ex in EXITS:
                row[ex] = deal(s, i, ex)
                p = [deal(s, j, ex) for j in (idx_at(s, r.t - d * DAY) for d in PL) if j is not None]
                p = [v for v in p if v is not None]
                row["pl_" + ex] = np.mean(p) if p else np.nan
            for h in HZ:
                row[f"r{h}"] = rel(s, te, h)
            rows.append(row)
    return pd.DataFrame(rows), R


def line(lab, x, col):
    x = x[x[col].notna()]
    if len(x) < 8:
        return f"    {lab:44s} мало ({len(x)})"
    m, t, n = ct(x[col], x.t)
    h1, h2 = x[x.t < CUT][col], x[x.t >= CUT][col]
    pl = x["pl_" + col].mean() if "pl_" + col in x else np.nan
    return (f"    {lab:44s} n={n:5d} {m:+7.2%} (t {t:+5.1f}) в плюсе {(x[col] > 0).mean():4.0%} | половины {h1.mean():+7.2%}"
            f" ({len(h1)}) / {h2.mean():+7.2%} ({len(h2)})" + (f" | плацебо {pl:+7.2%}" if pl == pl else ""))


def diff_line(lab, x, mask, col):
    x = x[x[col].notna()]
    m = mask.loc[x.index].astype(bool)
    a, b = x[m], x[~m]
    if len(a) < 8 or len(b) < 8:
        return f"    {lab:44s} мало ({len(a)}/{len(b)})"
    d, t = cl_t(x[col], m.astype(float), (x.t // DAY).astype(int))
    hh = []
    for hm in (x.t < CUT, x.t >= CUT):
        xx = x[hm]; mm = m[hm]
        hh.append(xx[mm][col].mean() - xx[~mm][col].mean())
    return (f"    {lab:44s} {len(a):5d} {a[col].mean():+7.2%} против {len(b):5d} {b[col].mean():+7.2%} | разница {d:+7.2%}"
            f" (t {t:+5.1f}) | половины {hh[0]:+7.2%} / {hh[1]:+7.2%}")


def journals(R):
    """Г3: у сделок s20 — был ли пост канала по монете за 6 ч до входа (и какой группы)."""
    T = pd.read_pickle("s20/trades.pkl").copy()
    by = {s: x.sort_values("t") for s, x in R.groupby("s")}
    lo_t, hi_t = R.t.min(), R.t.max()
    for g in ("any", "dn_up", "up_up", "up_dn", "dn_dn"):
        T[g] = False
    T["cover"] = (T.te > lo_t + 6 * 3600) & (T.te <= hi_t)
    for k, r in T.iterrows():
        x = by.get(r.s)
        if x is None:
            continue
        w = x[(x.t < r.te) & (x.t >= r.te - 6 * 3600)]
        if len(w):
            T.at[k, "any"] = True
            for g in set(w.g):
                T.at[k, g] = True
    return T


def main():
    R = pd.read_pickle("s43/rows.pkl")
    print(f"Постов {len(R)}: {pd.to_datetime(R.t.min(), unit='s'):%Y-%m-%d} – {pd.to_datetime(R.t.max(), unit='s'):%Y-%m-%d}")
    E, R2 = events(R)
    print(f"Постов с фьючерсом Binance в окне свечей: {len(R2)}, монет {R2.s.nunique()}; событий {len(E)}")
    print(E.g.value_counts().to_string())
    E.to_pickle("s43/events.pkl")

    print("\n## Г1 — группы оповещений: шорт с закрытия свечи после поста; доход к рынку — в сторону шорта")
    for g, lab in GROUPS.items():
        x = E[E.g == g]
        print(f"\n  {lab}: событий {len(x)}")
        for ex in EXITS:
            print(line(ex, x, ex))
        for h in HZ:
            print(line(f"к рынку за {h} ч (шорт)", x, f"r{h}"))

    print("\n## Г2 — сила оповещения внутри групп (S_7_20 и доход к рынку за 24 ч)")
    for g, lab in GROUPS.items():
        x = E[E.g == g]
        print(f"\n  {lab}")
        for nm, mask in (("оценка 10 против 9", x.score == 10), ("🔥 против без 🔥", x.fire),
                         ("OI за 1 ч по модулю ≥ 10%", x.oi1h.abs() >= 10), ("первое за день (🔈1) против повторных", x.sig == 1)):
            for col in ("S_7_20", "r24"):
                print(diff_line(f"{nm}, {col}", x, mask, col))

    print("\n## Г3 — пост канала за 6 ч до входа в сделку журнала (s20)")
    T = journals(R2.assign(g=np.where(R2.dir > 0, "up_", "dn_") + np.where(R2.p1h > 0, "up", "dn")))
    T.to_pickle("s43/jr.pkl")
    T = T[T.cover]
    print(f"  сделок в окне постов: {len(T)}; с постом за 6 ч: {T['any'].sum()}")
    for g, lab in (("dn_up", "🔴 и цена ↑"), ("up_up", "🟢 и цена ↑"), ("up_dn", "🟢 и цена ↓"), ("dn_dn", "🔴 и цена ↓"),
                   ("any", "любой пост")):
        print(f"\n  {lab} — против сделок без поста за 6 ч")
        for name, x in [("все журналы", T)] + list(T.groupby("journal", sort=False)):
            sel = x[g] | ~x["any"]
            xx = x[sel].assign(t=x.te[sel])
            print(diff_line(name, xx, xx[g], "net"))


if __name__ == "__main__":
    main()
