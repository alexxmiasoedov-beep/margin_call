"""s153 — шорт перед начислением при высоком положительном фандинге (гипотеза — ВЫВОДЫ.md, записана до расчёта).
Событие: начисление T с интервалами 4–8 ч (текущий и прошлый), ставка прошлого начисления на 8 ч ≥ +0,05% (основной порог
+0,1%). Шорт T − 2 ч → T − 15 мин, стоп 5% (основная); для отчёта T − 1 ч, T − 45 мин и после начисления T + 15 мин → T + 2 ч 15;
хедж индексом альтов; плацебо — та же монета за 45/90/135 сут. Запуск в папке периода с MC_K/MC_F/MC_CUT:
python3 <repo>/research/s153/pre_test.py <период>; сводка из /home/user/mc_data: python3 … report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s141"):
    sys.path.insert(0, os.path.join(HERE, "..", p))

DAY, H1, OUT = 86400, 3600, "/home/user/mc_data"
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01"), "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-17", "2025-12-01")}
SKIP = {"BTC", "ETH", "USDC", "FDUSD", "BUSD", "TUSD", "USDP", "DAI", "EUR", "BTCDOM", "DEFI", "FOOTBALL", "BLUEBIRD"}


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def run(per):
    from common import K, funding, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    t0, t1 = ts(PER[per][0]), ts(PER[per][1])
    T_, I_ = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T_, a - 900, "right")) - 1; j = int(np.searchsorted(T_, b - 900, "right")) - 1
        return I_[j] / I_[i] - 1 if 0 <= i <= j < len(I_) else np.nan

    def deal(s, te, hold_h):
        i = idx_at(s, te)
        if i is None or int(K[s]["t"][i]) + 900 != te:
            return None, np.nan
        x = trade(s, i, tp=None, sl=0.05, hold_h=hold_h, side=-1)
        if not x:
            return None, np.nan
        t_end = int(K[s]["t"][i]) + 900 + int(x["bars"]) * 900
        return x, x["net"] + mv(te, t_end)

    rows = []
    for s in K:
        if s in SKIP:
            continue
        lo, hi = live(s)
        if not np.isfinite(lo):
            continue
        fr = funding(s)
        if len(fr) < 3:
            continue
        t, r = fr[:, 0].astype(np.int64), fr[:, 1]
        for i in range(2, len(t)):
            T = int(t[i])
            if not (t0 <= T < t1) or T - 2 * H1 < lo + DAY or T + 3 * H1 > hi:
                continue
            I0, Ip = T - int(t[i - 1]), int(t[i - 1]) - int(t[i - 2])
            if not (4 * H1 - 60 <= I0 <= 8 * H1 + 60 and 4 * H1 - 60 <= Ip <= 8 * H1 + 60):
                continue
            r8 = float(r[i - 1]) * 8 * H1 / Ip
            if r8 < 0.0005:
                continue
            x, h = deal(s, T - 2 * H1, 1.75)
            if not x:
                continue
            a1, _ = deal(s, T - H1, 0.75)
            a2, _ = deal(s, T - 2700, 0.5)
            a3, _ = deal(s, T + 900, 2)
            pl = [w["net"] for w in (deal(s, T - 2 * H1 - dd * DAY, 1.75)[0] for dd in (45, 90, 135)) if w]
            rows.append(dict(s=s, t=T - 2 * H1, T=T, r8=r8, rate=float(r[i]), net=x["net"], why=x["why"], hed=h,
                             w60=a1["net"] if a1 else np.nan, w45=a2["net"] if a2 else np.nan, post=a3["net"] if a3 else np.nan,
                             pl=np.mean(pl) if pl else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s153_{per}.pkl")
    print(per, "событий", len(X), "≥ 0,1%:", int((X.r8 >= 0.001).sum()), flush=True)


def report():
    from oi_test import ct  # noqa: E402
    A = []
    for per, (a, b, cut) in PER.items():
        X = pd.read_pickle(f"{OUT}/s153_{per}.pkl"); X["per"] = per; A.append(X)
        months = (ts(b) - ts(a)) / (30.4 * DAY); c = ts(cut)
        print(f"\n{per}:")
        for name, x in (("≥ +0,1% (основная)", X[X.r8 >= 0.001]), ("+0,05…+0,1%", X[X.r8 < 0.001]), ("≥ +0,2%", X[X.r8 >= 0.002])):
            m, t, n = ct(x.net, x.t); mh, th, _ = ct(x.hed.dropna(), x.t[x.hed.notna()])
            m60, _, _ = ct(x.w60.dropna(), x.t[x.w60.notna()]); m45, _, _ = ct(x.w45.dropna(), x.t[x.w45.notna()])
            mp, tp_, _ = ct(x.post.dropna(), x.t[x.post.notna()])
            dp = (x.net - x.pl).dropna(); md, td, _ = ct(dp, x.t[(x.net - x.pl).notna()])
            print(f"  {name:20s} n={n:6d} ({n / months:4.0f}/мес) T−2ч→T−15 {m:+.3%} (t {t:+.1f}) | половины "
                  f"{x[x.t < c].net.mean():+.3%} / {x[x.t >= c].net.mean():+.3%} | с хеджем {mh:+.3%} (t {th:+.1f}) | "
                  f"T−1ч {m60:+.3%} | T−45 {m45:+.3%} | после T {mp:+.3%} (t {tp_:+.1f}) | плацебо {x.pl.mean():+.3%}, "
                  f"сверх {md:+.3%} (t {td:+.1f})")
    A = pd.concat(A, ignore_index=True); x = A[A.r8 >= 0.001]
    m, t, n = ct(x.net, x.t); mh, th, _ = ct(x.hed.dropna(), x.t[x.hed.notna()])
    dp = (x.net - x.pl).dropna(); md, td, _ = ct(dp, x.t[(x.net - x.pl).notna()])
    print(f"\nшесть лет, основная: n={n} {m:+.3%} (t {t:+.1f}), с хеджем {mh:+.3%} (t {th:+.1f}), сверх плацебо {md:+.3%} (t {td:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
