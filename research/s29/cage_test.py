"""s29 — проверка гипотез Г1–Г3 (ВЫВОДЫ.md, записаны до проверки) на событиях s29/cages.pkl (cage_events.py).
Г1: доля садков, где премия на бирже за первые 7 сут закрытия (или до открытия) хотя бы раз ≥ 10%, против окон той же длины
у той же монеты за 45/90/135 сут до.
Г2: премия в садке впервые ≥ порога → шорт фьючерса Binance на закрытии следующего часа, 7 сут, стоп +50%, без тейка,
комиссия 0,1%, фактический фандинг (s15/common.trade); одна сделка на монету, пока открыта прошлая; плацебо — та же
монета за 45/90/135 сут до, тот же час; половины до и после 01.12.2025; t по дням. Пороги 10% (основной), 5%, 20%;
сроки 7 сут (основной), 1 и 3 сут.
Г3: садки с премией ≥ 10% и известным концом → шорт с закрытия часа, в котором вышел пост об открытии, 7 сут, стоп +50%.
Пересечение с пампами 🇰🇷 (s15/kr_pumps.pkl) в пределах ±24 ч. Итог — s29/trades.pkl. Запуск из папки с данными."""
import os
import pickle
import sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "s15"))
from common import K, trade  # noqa: E402
from cage_events import premium, DAY, G, CB  # noqa: E402

CUT = 1764547200                                            # 01.12.2025
PL = (45, 90, 135)
E = pickle.load(open("s29/cages.pkl", "rb"))
PUMPS = pickle.load(open("s15/kr_pumps.pkl", "rb"))
_mk = {}


def mk(h):
    if h not in _mk:
        with np.errstate(all="ignore"):
            _mk[h] = np.r_[np.nanmedian(CB[:, h:] / CB[:, :-h] - 1, axis=0), np.full(h, np.nan)]
    return _mk[h]


def ct(x, T):
    d = pd.Series(np.asarray(x, float), index=pd.to_datetime(np.asarray(T), unit="s").date).dropna()
    if len(d) < 5:
        return np.nan, np.nan, len(d)
    q = d.groupby(level=0).mean()
    return d.mean(), (q.mean() / q.std() * np.sqrt(len(q)) if len(q) > 2 and q.std() > 0 else np.nan), len(d)


def idx(s, te):
    """Индекс 15-мин свечи, закрывающейся в момент te; None — нет свечи."""
    t = K[s]["t"]; i = int(np.searchsorted(t, te - 900))
    return i if i < len(t) and t[i] == te - 900 else None


def short(s, te, hold_h):
    i = idx(s, te)
    if i is None:
        return None
    r = trade(s, i, tp=None, sl=0.5, hold_h=hold_h, side=-1)
    if r is None:
        return None
    k = int(np.searchsorted(G, te))
    m = mk(hold_h)[k] if k < len(G) and G[k] == te else np.nan
    return dict(net=r["net"], why=r["why"], rel=r["net"] + m)


def g1():
    ev, pl = [], []
    for r in E.itertuples():
        if r.path is None:
            continue
        stop = min(r.start + 7 * DAY, r.end) if np.isfinite(r.end) else r.start + 7 * DAY
        tc, pr, _ = r.path
        w = (tc > r.start) & (tc <= stop)
        if not np.isfinite(pr[w]).any():
            continue
        ev.append(np.nanmax(pr[w]) >= 0.10)
        for d in PL:
            p = premium(r.ex, r.coin, r.s, r.mult, r.start - d * DAY, stop - d * DAY)
            if p is not None and np.isfinite(p[1]).any():
                pl.append(np.nanmax(p[1]) >= 0.10)
    print(f"Г1: премия ≥ 10% хотя бы раз — в садках {np.mean(ev):.1%} из {len(ev)}; "
          f"в окнах той же длины за 45/90/135 сут до — {np.mean(pl):.1%} из {len(pl)}")


def entries(col):
    """Входы по порогу: время закрытия часа со скачком + 1 ч; одна сделка на монету, пока открыта прошлая (7 сут)."""
    X = E[E[col].notna()].copy()
    X["te"] = X[col] + 3600
    X = X.sort_values("te")
    keep, last = [], {}
    for r in X.itertuples():
        if r.te - last.get(r.s, -np.inf) < 7 * DAY:
            continue
        last[r.s] = r.te; keep.append(r.Index)
    return X.loc[keep]


def pumped(s, te):
    if s not in PUMPS or not len(PUMPS[s]):
        return False
    tp = K[s]["t"][PUMPS[s]].astype(float)
    return bool((np.abs(tp - te) <= DAY).any())


def run(X, hold_h, label):
    rows = []
    for r in X.itertuples():
        a = short(r.s, r.te, hold_h)
        if a is None:
            continue
        p = [short(r.s, r.te - d * DAY, hold_h) for d in PL]
        p = [x["net"] for x in p if x]
        rows.append(dict(ex=r.ex, coin=r.coin, s=r.s, te=r.te, net=a["net"], rel=a["rel"], why=a["why"],
                         plac=np.mean(p) if p else np.nan, kr=pumped(r.s, r.te), pmax=r.pmax))
    D = pd.DataFrame(rows)
    if D.empty:
        print(f"  {label}: сделок нет"); return D
    m, t, n = ct(D.net, D.te)
    h1, h2 = D[D.te < CUT].net, D[D.te >= CUT].net
    print(f"  {label}: n={n:3d} {m:+.2%} (t {t:+.1f}), медиана {D.net.median():+.2%}, в плюсе {(D.net > 0).mean():.0%}, "
          f"стопов {(D.why == 'стоп').mean():.0%} | половины {h1.mean():+.2%} ({len(h1)}) / {h2.mean():+.2%} ({len(h2)}) | "
          f"к рынку {D.rel.mean():+.2%} | плацебо {D.plac.mean():+.2%} | на пампах 🇰🇷 ±24 ч: {D.kr.sum()}")
    return D


if __name__ == "__main__":
    g1()
    res = {}
    print("\nГ2: премия в садке впервые ≥ порога → шорт фьючерса на закрытии следующего часа")
    for thr in (10, 5, 20):
        X = entries(f"t{thr}")
        for h in ((168, 24, 72) if thr == 10 else (168,)):
            res[(thr, h)] = run(X, h, f"порог {thr}%, {h // 24} сут")
    print("\nГ3: открытие ввода (садки с премией ≥ 10% и известным концом) → шорт с закрытия часа поста об открытии, 7 сут")
    Y = E[(E.pmax >= 0.10) & E.end.notna()].copy()
    Y["te"] = (Y.end // 3600 + 1) * 3600
    res["g3"] = run(Y, 168, "открытие")
    pickle.dump(res, open("s29/trades.pkl", "wb"))
    D = res[(10, 168)]
    if not D.empty:
        pd.set_option("display.width", 220)
        print("\nСделки основного правила:")
        print(D.assign(te=pd.to_datetime(D.te, unit="s").dt.strftime("%y-%m-%d %H"), net=(D.net * 100).round(1),
                       rel=(D.rel * 100).round(1), plac=(D.plac * 100).round(1), pmax=(D.pmax * 100).round(0))
              .to_string(index=False))
