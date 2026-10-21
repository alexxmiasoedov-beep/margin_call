"""Пампы монет «только фьючерс» (на споте Binance нет пары к USDT на момент пампа) против монет со спотом. Шорт 10/25/48 ч (bt2y)."""
import pickle, re, datetime
import numpy as np, pandas as pd
import bv
from concurrent.futures import ThreadPoolExecutor
syms = set(open("s2/spot_syms.txt").read().split())
D = pd.read_pickle("s3/pump_IDR.pkl")[["s", "t", "pnl", "korea", "kshare", "tshare"]]
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
def first_spot(s):
    for name in (s, strip(s)):
        if f"{name}USDT" in syms:
            for m in ("2017-08", "2018-01", "2019-01", "2020-01", "2021-01", "2022-01", "2023-01", "2024-01", "2024-06", "2024-10", "2025-01", "2025-04", "2025-07", "2025-10", "2026-01", "2026-04", "2026-07", "2026-09"):
                r = bv.rows(bv.fetch_spot(f"monthly/klines/{name}USDT/1d/{name}USDT-1d-{m}.zip"))
                if r: return s, int(r[0][0]) // (1000000 if len(r[0][0]) > 13 else 1000)
            return s, 0
    return s, None
with ThreadPoolExecutor(16) as ex: FS = dict(ex.map(first_spot, sorted(D.s.unique())))
D["spot"] = [FS.get(s) is not None and FS.get(s) <= t for s, t in zip(D.s, D.t)]
D["year"] = np.where(D.t < datetime.datetime(2025, 10, 1, tzinfo=datetime.timezone.utc).timestamp(), "1-й год", "2-й год")
D["q"] = pd.to_datetime(D.t, unit="s").dt.to_period("Q").astype(str)
def show(name, m):
    d = D[m]; y = d.groupby("year").pnl.mean() * 100; qm = d.groupby("q").pnl.mean()
    print(f"{name:52s} {len(d):5d} | шорт {d.pnl.mean() * 100:+.2f}% | {y.get('1-й год', np.nan):+.2f}/{y.get('2-й год', np.nan):+.2f} | кв.+ {(qm > 0).sum()}/{len(qm)}")
other = ~(D.korea & (D.kshare >= 0.2)) & ~(D.tshare >= 0.1)
show("все пампы", D.pnl.notna()); show("есть спот Binance (USDT)", D.spot); show("только фьючерс", ~D.spot)
show("только фьючерс, без корейского/турецкого сигнала", ~D.spot & other); show("только фьючерс и нет в Корее", ~D.spot & ~D.korea)
show("есть спот, без корейского/турецкого сигнала", D.spot & other)
D.to_pickle("s3/pump_spot.pkl")
