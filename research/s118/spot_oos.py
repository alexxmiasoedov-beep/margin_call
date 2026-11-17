"""s118 — 🛒 вне выборки 10.2022–09.2024: правило s49/spot_test.py без изменений. Пампы — s15/kr_panel.pumps (+15% за ≤ 2 ч
из покоя, раз в сутки) на s117/k_oos.pkl; доля спота Binance — оборот пары XXXUSDT за последний полный час до закрытия
свечи пампа ÷ (спот + фьючерс); граница 25,9% — из первой половины 2024–2026 гг. Шорт 10/25/48, одна сделка на монету
за 48 ч, плацебо — та же монета за 45/90/135 сут. Часовые свечи спота за 2022–2024 гг. — архив Binance (кэш s23/spotcache
в рабочей папке). Запуск из ~/mc_oos: MC_K=… MC_F=… MC_CUT=2023-10-01 python3 <repo>/research/s118/spot_oos.py"""
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s23"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
os.makedirs("s23/spotcache", exist_ok=True)
from common import K, trade  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402
from kr_panel import pumps  # noqa: E402

sys.modules.pop("spot_fetch", None)
import importlib.util  # noqa: E402
spec = importlib.util.spec_from_file_location("sf", os.path.join(HERE, "..", "s23", "spot_fetch.py"))
OOS = [f"2022-{m:02d}" for m in (10, 11, 12)] + [f"2023-{m:02d}" for m in range(1, 13)] + [f"2024-{m:02d}" for m in range(1, 10)]
EX = dict(tp=0.10, sl=0.25, hold_h=48)
Q2 = 0.259


def spot_series(s, get, rows):
    for b in (s, re.sub(r"^(1000000|100000|10000|1000)", "", s)):
        if any(get(f"monthly/klines/{b}USDT/1h/{b}USDT-1h-{m}.zip") for m in ("2023-06", "2024-06", "2022-12")):
            out = []
            for m in OOS:
                out += rows(get(f"monthly/klines/{b}USDT/1h/{b}USDT-1h-{m}.zip"))
            return np.array(sorted(set(out))) if out else None
    return None


def main():
    src = open(spec.origin).read().split("if __name__")[0].replace('CSY = pickle.load(open("s22/grid.pkl", "rb"))["syms"]', "CSY = []")
    ns = {}
    exec(compile(src, spec.origin, "exec"), ns)
    get, rows = ns["get"], ns["rows"]
    syms = [s for s in K if s not in ("BTC", "ETH")]
    with ThreadPoolExecutor(16) as ex:
        SP = {s: a for s, a in zip(syms, ex.map(lambda s: spot_series(s, get, rows), syms)) if a is not None}
    print(f"монет со спотом Binance: {len(SP)} из {len(syms)}", flush=True)
    out = []
    for s in syms:
        a = K[s]
        pj = pumps(a)
        if not len(pj):
            continue
        Tend = a["t"].astype(np.int64) + 900
        H = ((Tend - 1) // 3600 + 1) * 3600
        perp = pd.Series(a["qv"].astype(float)).groupby(H).sum()
        sp = SP.get(s)
        spv = pd.Series(sp[:, 1], index=sp[:, 0].astype(np.int64) + 3600) if sp is not None else None
        last = -1e18
        for j in pj:
            Tp = int(a["t"][j]) + 900
            if Tp - last < 48 * 3600:
                continue
            Hh = (Tp // 3600) * 3600
            share = np.nan
            if spv is not None:
                v = float(spv.get(Hh, np.nan)); pv = float(perp.get(Hh, np.nan))
                if v == v and pv == pv:
                    share = v / max(v + pv, 1.0)
            x = trade(s, j, **EX)
            if x is None:
                continue
            last = Tp
            p = [y["net"] for dd in (45, 90, 135) if j - dd * 96 >= 96 and (y := trade(s, j - dd * 96, **EX))]
            out.append(dict(s=s, t=Tp, share=share, net=x["net"], pl=np.mean(p) if p else np.nan))
    X = pd.DataFrame(out)
    X.to_pickle("s118_spot.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    for lab, x in (("все пампы", X), ("доля спота ≥ 25,9% (🛒)", X[X.share >= Q2]), ("доля спота < 25,9%", X[X.share < Q2]),
                   ("без спота Binance", X[X.share.isna()])):
        m, t, n = ct(x.net, x.t); dp, tp, _ = ct(x.net - x.pl, x.t)
        h1, h2 = x[x.t < CUT], x[x.t >= CUT]
        print(f"  {lab:26s} n={n:4d} ({n / months:5.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x.net > 0).mean():3.0%} | "
              f"половины {h1.net.mean():+6.2%} ({len(h1)}) / {h2.net.mean():+6.2%} ({len(h2)}) | плацебо {x.pl.mean():+6.2%}, "
              f"разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
