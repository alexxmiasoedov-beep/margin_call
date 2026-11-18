"""s155 — прокол максимума прошлых суток (PDH) с возвратом в том же часе → шорт (гипотеза — ВЫВОДЫ.md, записана до расчёта).
Вселенная — 100 самых торгуемых альт-перпов за 30 сут. Часовые свечи из 15-мин (s135/reset_test.hourly), дельта часа —
Σ(2·tb − qv). Основная сделка: шорт на закрытии часа, стоп = максимум часа + 0,5%, 24 ч. Для отчёта: стоп 5%, 4 ч, 48 ч,
дельта < 0, прокол недельного максимума (PWH), хедж индексом альтов, плацебо. Запуск в папке периода с MC_K/MC_F/MC_CUT:
python3 <repo>/research/s155/sweep_test.py <период>; сводка из /home/user/mc_data: python3 … report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s141", "s135"):
    sys.path.insert(0, os.path.join(HERE, "..", p))

DAY, H1, OUT = 86400, 3600, "/home/user/mc_data"
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01"), "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-17", "2025-12-01")}


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def run(per):
    from common import K, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    import reset_test as R  # noqa: E402
    t0, t1 = ts(PER[per][0]), ts(PER[per][1])
    T_, I_ = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T_, a - 900, "right")) - 1; j = int(np.searchsorted(T_, b - 900, "right")) - 1
        return I_[j] / I_[i] - 1 if 0 <= i <= j < len(I_) else np.nan

    SK = R.SKIP | {"BTC", "ETH"}
    days = np.arange(t0 - t0 % DAY, t1, DAY)
    vol = {}
    for s, a in K.items():
        if s in SK:
            continue
        lo, hi = live(s)
        if not np.isfinite(lo):
            continue
        cs = np.r_[0.0, np.cumsum(a["qv"].astype(float))]
        i1 = np.searchsorted(a["t"], days); i0 = np.searchsorted(a["t"], days - 30 * DAY)
        v = cs[i1] - cs[i0]; v[(days - 30 * DAY < lo) | (days > hi)] = 0; vol[s] = v
    S = list(vol); M = np.vstack([vol[s] for s in S])
    top = {int(d): {S[j] for j in np.argsort(-M[:, k])[:100] if M[j, k] > 0} for k, d in enumerate(days)}

    rows = []
    for s in S:
        a = K[s]; hr = R.hourly(a); t = hr["t"]
        q = a["qv"].astype(float); tb = a["tb"].astype(float)
        off = int(((-int(a["t"][0])) % 3600) // 900); n = len(t)
        dlt = (2 * tb - q)[off:off + 4 * n].reshape(n, 4).sum(1)
        f0 = int(np.argmax(t % DAY == 0)) if np.any(t % DAY == 0) else None
        if f0 is None:
            continue
        nd = (n - f0) // 24
        if nd < 8:
            continue
        sl_ = slice(f0, f0 + 24 * nd)
        Hh, Cc, Qq, Tt = (hr[k][sl_].reshape(nd, 24) for k in ("h", "c", "qv", "t"))
        Dd = dlt[sl_].reshape(nd, 24)
        for k in range(7, nd):
            D = int(Tt[k, 0])
            if not (t0 <= D < t1) or s not in top.get(D, ()) or Qq[k - 1].min() <= 0:
                continue
            pdh = Hh[k - 1].max()
            pwh = Hh[k - 7:k].max() if Qq[k - 7:k].min() > 0 else np.nan
            above = np.flatnonzero(Hh[k] > pdh)
            if not len(above):
                continue
            jh = int(above[0])
            if Cc[k, jh] >= pdh or Qq[k, jh] <= 0:
                continue
            i = f0 + 24 * k + jh
            te = int(t[i]) + H1
            j = idx_at(s, te)
            if j is None or int(a["t"][j]) + 900 != te:
                continue
            sl = float(hr["h"][i] * 1.005 / a["c"][j] - 1)
            x = trade(s, j, tp=None, sl=sl, hold_h=24, side=-1)
            if not x:
                continue
            t_end = int(a["t"][j]) + 900 + int(x["bars"]) * 900
            y5 = trade(s, j, tp=None, sl=0.05, hold_h=24, side=-1)
            y4 = trade(s, j, tp=None, sl=sl, hold_h=4, side=-1)
            y48 = trade(s, j, tp=None, sl=sl, hold_h=48, side=-1)
            pl = []
            for back in (45, 90, 135):
                jj = idx_at(s, te - back * DAY)
                w = trade(s, jj, tp=None, sl=sl, hold_h=24, side=-1) if jj is not None else None
                if w:
                    pl.append(w["net"])
            rows.append(dict(s=s, t=te, sl=sl, net=x["net"], why=x["why"], hed=x["net"] + mv(te, t_end),
                             n5=y5["net"] if y5 else np.nan, n4=y4["net"] if y4 else np.nan, n48=y48["net"] if y48 else np.nan,
                             dneg=bool(Dd[k, jh] < 0), pwh=bool(np.isfinite(pwh) and Hh[k, jh] > pwh and Cc[k, jh] < pwh),
                             pl=np.mean(pl) if pl else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s155_{per}.pkl")
    print(per, "событий", len(X), flush=True)


def report():
    from oi_test import ct  # noqa: E402
    A = []
    for per, (a, b, cut) in PER.items():
        X = pd.read_pickle(f"{OUT}/s155_{per}.pkl"); X["per"] = per; A.append(X)
        months = (ts(b) - ts(a)) / (30.4 * DAY); c = ts(cut)
        print(f"\n{per}: медиана стопа {X.sl.median():.1%}")
        for name, x in (("все проколы PDH (основная)", X), ("с дельтой < 0", X[X.dneg]), ("прокол PWH", X[X.pwh])):
            m, t, n = ct(x.net, x.t); mh, th, _ = ct(x.hed.dropna(), x.t[x.hed.notna()])
            m5, _, _ = ct(x.n5.dropna(), x.t[x.n5.notna()]); m4, _, _ = ct(x.n4.dropna(), x.t[x.n4.notna()])
            m48, t48, _ = ct(x.n48.dropna(), x.t[x.n48.notna()])
            dp = (x.net - x.pl).dropna(); md, td, _ = ct(dp, x.t[(x.net - x.pl).notna()])
            print(f"  {name:26s} n={n:6d} ({n / months:4.0f}/мес) 24 ч {m:+.2%} (t {t:+.1f}) | половины {x[x.t < c].net.mean():+.2%} / "
                  f"{x[x.t >= c].net.mean():+.2%} | стопов {(x.why == 'стоп').mean():.0%} | с хеджем {mh:+.2%} (t {th:+.1f}) | "
                  f"стоп 5% {m5:+.2%} | 4 ч {m4:+.2%} | 48 ч {m48:+.2%} (t {t48:+.1f}) | сверх плацебо {md:+.2%} (t {td:+.1f})")
    A = pd.concat(A, ignore_index=True)
    m, t, n = ct(A.net, A.t); mh, th, _ = ct(A.hed.dropna(), A.t[A.hed.notna()])
    print(f"\nшесть лет: n={n} {m:+.2%} (t {t:+.1f}), с хеджем {mh:+.2%} (t {th:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
