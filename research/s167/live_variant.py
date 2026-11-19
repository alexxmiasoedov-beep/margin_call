"""s167 — правило для бота: «первое событие монеты за 48 ч» только среди заводов на Binance (боту не нужно следить за всеми
5331 адресом бирж) против правила бэктеста (первое среди заводов на все биржи, если оно на Binance). Ход фьючерса за 24 ч
−5…+5%, шорт 24 ч, стоп +25%. Запуск в папке периода с MC_K/MC_F/MC_CUT: python3 <repo>/research/s167/live_variant.py <период>;
сводка из /home/user/mc_data: python3 … report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
OUT, DAY = "/home/user/mc_data", 86400
PER = {"2020–2022": ("2020-10-01", "2022-10-01"), "2022–2024": ("2022-10-01", "2024-10-01"), "2024–2026": ("2024-10-01", "2026-10-17")}


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def first48(E):
    keep, last = np.zeros(len(E), bool), {}
    for i, r in enumerate(E.itertuples()):
        if r.t - last.get(r.perp, -10 ** 12) >= 48 * 3600:
            keep[i] = True; last[r.perp] = r.t
    return keep


def run(per):
    from common import K, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    t0, t1 = ts(PER[per][0]), ts(PER[per][1])
    E = pd.read_pickle(f"{OUT}/s160_events.pkl").sort_values("t").reset_index(drop=True)
    E["A"] = E.first_all & (E.exch == "Binance")                       # правило бэктеста
    B = E[E.exch == "Binance"].copy(); B["B"] = first48(B)             # только Binance
    E = E.merge(B[["tx", "li", "B"]], on=["tx", "li"], how="left"); E["B"] = E.B.fillna(False).astype(bool)
    rows = []
    for r in E[E.A | E.B].itertuples():
        te = int(-(-(int(r.t) + 900) // 900) * 900)
        if not (t0 <= te < t1) or r.perp not in K:
            continue
        lo, hi = live(r.perp)
        if not np.isfinite(lo) or te < lo + DAY:
            continue
        i = idx_at(r.perp, te)
        if i is None or int(K[r.perp]["t"][i]) + 900 != te:
            continue
        j = idx_at(r.perp, te - DAY)
        if j is None or int(K[r.perp]["t"][j]) + 900 != te - DAY:
            continue
        r24 = float(K[r.perp]["c"][i]) / float(K[r.perp]["c"][j]) - 1
        x = trade(r.perp, i, tp=None, sl=0.25, hold_h=24, side=-1)
        if x:
            rows.append(dict(s=r.perp, t=te, A=bool(r.A), B=bool(r.B), r24=r24, net=x["net"]))
    X = pd.DataFrame(rows); X.to_pickle(f"{OUT}/s167lv_{per}.pkl")
    print(per, "сделок A", int(X.A.sum()), "B", int(X.B.sum()), flush=True)


def report():
    from oi_test import ct  # noqa: E402
    for per in PER:
        X = pd.read_pickle(f"{OUT}/s167lv_{per}.pkl"); C = X[X.r24.abs() <= 0.05]
        a, b = C[C.A], C[C.B]
        ma, ta, na = ct(a.net, a.t); mb, tb, nb = ct(b.net, b.t)
        print(f"{per}: спокойный рынок — бэктест (все биржи) n={na} {ma:+.2%} (t {ta:+.1f}) | бот (только Binance) n={nb} {mb:+.2%} "
              f"(t {tb:+.1f}) | общих {int((C.A & C.B).sum())}, только у бота {int((C.B & ~C.A).sum())} "
              f"({C[C.B & ~C.A].net.mean():+.2%}), только в бэктесте {int((C.A & ~C.B).sum())}")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
