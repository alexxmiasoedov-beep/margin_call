"""s135 — скачок ≥ 5% за час 00–01 UTC у монет без рынка к воне (гипотеза — ВЫВОДЫ.md, записана до расчёта).
Часовые свечи — из 15-мин архива периода (MC_K), фандинг — MC_F; «рынок к воне есть» — у монеты есть строка часа
в s15/kr_panel.pkl папки периода. Шорт в 01:00 UTC, 10/25/48 (s88/oos_test.trade1h). Контроль — те же пороги в другие часы
(не чаще раза в сутки на монету), плацебо — та же монета за 45/90/135 сут в тот же час.
Запуск в папке периода: MC_K=… MC_F=… MC_CUT=… python3 <repo>/research/s135/reset_test.py <период>;
сводка: python3 <repo>/research/s135/reset_test.py report"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s88"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from oi_test import ct  # noqa: E402

DAY, H1 = 86400, 3600
OUT = "/home/user/mc_data"
PERIODS = {"2020–2022": "2021-10-01", "2022–2024": "2023-10-01", "2024–2026": "2025-12-01"}
SKIP = {"BTC", "ETH", "USDC", "FDUSD", "BUSD", "TUSD", "USDP", "DAI", "EUR", "BTCDOM", "DEFI", "FOOTBALL", "BLUEBIRD"}


def hourly(a):
    t = a["t"]
    off = int(((-int(t[0])) % 3600) // 900)
    n = (len(t) - off) // 4
    sl = slice(off, off + 4 * n)
    r = lambda k: a[k][sl].astype(float).reshape(n, 4)
    return {"t": t[sl].reshape(n, 4)[:, 0].astype(np.int64), "o": r("o")[:, 0], "h": r("h").max(1), "l": r("l").min(1),
            "c": r("c")[:, 3], "qv": r("qv").sum(1)}


def run(per):
    from common import K, funding, live  # noqa: E402
    from oos_test import trade1h  # noqa: E402
    P = pickle.load(open("s15/kr_panel.pkl", "rb"))
    kor = {s: set((d["T"].values.astype(np.int64) - H1).tolist()) for s, d in P.items()}
    rows = []
    for s in K:
        if s in SKIP:
            continue
        lo, hi = live(s)
        if not np.isfinite(lo):
            continue
        a = hourly(K[s]); t = a["t"]
        fr = np.asarray(funding(s), float)
        fr = fr if fr.ndim == 2 and len(fr) else np.zeros((0, 2))
        r1 = np.r_[np.nan, a["c"][1:] / a["c"][:-1] - 1]
        ok = (t >= lo + DAY) & (t + H1 <= hi) & (a["qv"] > 0)
        ks, last = kor.get(s, set()), -10 ** 18
        for i in np.flatnonzero(ok & (r1 >= 0.05)):
            H = int(t[i])
            if H in ks:                                       # у монеты в этот час есть рынок к воне
                continue
            open0 = H % DAY == 0
            if not open0:
                if H - last < DAY:
                    continue
                last = H
            x = trade1h(a, fr, int(i), tp=0.10, sl=0.25, hold_h=48)
            if x is None:
                continue
            pl = []
            for dd in (45, 90, 135):
                k = int(i) - dd * 24
                if k >= 1 and t[k] == H - dd * DAY and a["qv"][k] > 0:
                    y = trade1h(a, fr, k, tp=0.10, sl=0.25, hold_h=48)
                    if y is not None:
                        pl.append(y)
            rows.append(dict(s=s, t=H + H1, open0=open0, r1=float(r1[i]), net=float(x), pl=np.mean(pl) if pl else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s135_{per}.pkl")
    print(per, "событий", len(X), "из них в 00–01 UTC", int(X.open0.sum()))


def diff(a, b):
    da = a.groupby(pd.to_datetime(a.t, unit="s").dt.date).net.mean()
    db = b.groupby(pd.to_datetime(b.t, unit="s").dt.date).net.mean()
    d = a.net.mean() - b.net.mean(); se = np.sqrt(da.var() / len(da) + db.var() / len(db))
    return d, d / se


def report():
    A = []
    for per, cut in PERIODS.items():
        X = pd.read_pickle(f"{OUT}/s135_{per}.pkl"); X["per"] = per
        c = pd.Timestamp(cut, tz="UTC").timestamp()
        months = (X.t.max() - X.t.min()) / (30.4 * DAY)
        o, r = X[X.open0], X[~X.open0]
        m, t, n = ct(o.net, o.t); d, td = diff(o, r)
        dp = (o.net - o.pl).dropna()
        print(f"{per}: 00–01 UTC n={n} ({n / months:.1f}/мес) {m:+.2%} (t {t:+.1f}) в плюсе {(o.net > 0).mean():.0%} | половины "
              f"{o[o.t < c].net.mean():+.2%} / {o[o.t >= c].net.mean():+.2%} | сверх плацебо {dp.mean():+.2%} ({len(dp)})"
              f" | другие часы {len(r)}: {r.net.mean():+.2%}, разница {d:+.2%} (t {td:+.1f})")
        A.append(X)
    A = pd.concat(A, ignore_index=True)
    o, r = A[A.open0], A[~A.open0]
    m, t, n = ct(o.net, o.t); d, td = diff(o, r)
    print(f"шесть лет: 00–01 UTC n={n} {m:+.2%} (t {t:+.1f}); другие часы {r.net.mean():+.2%}; разница {d:+.2%} (t {td:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
