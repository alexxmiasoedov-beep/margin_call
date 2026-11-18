"""s163 — скачок обращения CMC за сутки ≥ 1% → шорт с 00:15 UTC следующих суток на 48 ч (гипотеза — ВЫВОДЫ.md, записана
до расчёта). Обращение — s160/circ/<id>.json (CMC data-api), токены — s160/cmc_ids.json. Запуск в папке периода с MC_K/MC_F:
python3 <repo>/research/s163/circ_test.py <период>; сводка из /home/user/mc_data: python3 … report"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s141"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
OUT, DAY = "/home/user/mc_data", 86400
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01"), "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-17", "2025-12-01")}


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def run(per):
    from common import K, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    t0, t1 = ts(PER[per][0]), ts(PER[per][1])
    T_, I_ = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T_, a - 900, "right")) - 1; j = int(np.searchsorted(T_, b - 900, "right")) - 1
        return I_[j] / I_[i] - 1 if 0 <= i <= j < len(I_) else np.nan

    ids = json.load(open(f"{OUT}/s160/cmc_ids.json"))
    rows = []
    for tok, v in ids.items():
        s = v["perp"]; p = f"{OUT}/s160/circ/{v['id']}.json"
        if s not in K or not os.path.exists(p):
            continue
        lo, hi = live(s)
        if not np.isfinite(lo):
            continue
        c = pd.Series({d: x for d, x, _ in json.load(open(p)) if x}).sort_index()
        c.index = pd.to_datetime(c.index)
        g = c / c.shift(1) - 1
        last = -10 ** 12
        for d, jump in g.items():
            if not np.isfinite(jump) or jump < 0.005:
                continue
            te = int(d.timestamp()) + DAY + 900                 # 00:15 UTC следующих суток
            if not (t0 <= te < t1) or te < lo + DAY or te - last < 7 * DAY:
                continue
            i = idx_at(s, te)
            if i is None or int(K[s]["t"][i]) + 900 != te:
                continue
            x = trade(s, i, tp=None, sl=0.25, hold_h=48, side=-1)
            if not x:
                continue
            last = te
            y = trade(s, i, tp=None, sl=0.25, hold_h=24, side=-1)
            t_end = int(K[s]["t"][i]) + 900 + int(x["bars"]) * 900
            pl = [w["net"] for w in (trade(s, j, tp=None, sl=0.25, hold_h=48, side=-1) for j in
                                     (idx_at(s, te - b * DAY) for b in (45, 90, 135)) if j is not None) if w]
            rows.append(dict(s=s, t=te, jump=float(jump), net=x["net"], why=x["why"], n24=y["net"] if y else np.nan,
                             hed=x["net"] + mv(te, t_end), pl=np.mean(pl) if pl else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s163_{per}.pkl")
    print(per, "событий ≥ 0,5%:", len(X), "≥ 1%:", int((X.jump >= 0.01).sum()) if len(X) else 0, flush=True)


def report():
    from oi_test import ct  # noqa: E402
    A = []
    for per, (a, b, cut) in PER.items():
        X = pd.read_pickle(f"{OUT}/s163_{per}.pkl"); X["per"] = per; A.append(X)
        months = (ts(b) - ts(a)) / (30.4 * DAY); c = ts(cut)
        print(f"\n{per}:")
        for name, x in (("≥ 1% (основная)", X[X.jump >= 0.01]), ("0,5–1%", X[X.jump < 0.01]), ("≥ 2%", X[X.jump >= 0.02]),
                        ("≥ 5%", X[X.jump >= 0.05])):
            if len(x) < 8:
                print(f"  {name}: n={len(x)}"); continue
            m, t, n = ct(x.net, x.t); mh, th, _ = ct(x.hed.dropna(), x.t[x.hed.notna()]); m24, _, _ = ct(x.n24.dropna(), x.t[x.n24.notna()])
            dp = (x.net - x.pl).dropna(); md, td, _ = ct(dp, x.t[(x.net - x.pl).notna()])
            print(f"  {name:16s} n={n:5d} ({n / months:4.1f}/мес) 48 ч {m:+.2%} (t {t:+.1f}) | половины {x[x.t < c].net.mean():+.2%} / "
                  f"{x[x.t >= c].net.mean():+.2%} | с хеджем {mh:+.2%} (t {th:+.1f}) | 24 ч {m24:+.2%} | сверх плацебо {md:+.2%} (t {td:+.1f})")
    A = pd.concat(A, ignore_index=True); x = A[A.jump >= 0.01]
    m, t, n = ct(x.net, x.t); mh, th, _ = ct(x.hed.dropna(), x.t[x.hed.notna()])
    print(f"\nшесть лет, ≥ 1%: n={n} {m:+.2%} (t {t:+.1f}), с хеджем {mh:+.2%} (t {th:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
