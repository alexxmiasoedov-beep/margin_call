"""s259, вопрос 4 — ликвидации Binance по каналу t.me/s/BinanceLiquidations (s72/liq.jsonl: сообщения о ликвидациях
от ~50 тыс. $, 19.09.2024–17.11.2026) у перпов без спота против монет со спотом: частота, сторона (лонги / шорты),
ликвидации к обороту, каскады (≥ 3 ликвидации одной стороны или ≥ 0,5 млн $ за 60 мин). Доходы не считаются.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s259/study/liq.py"""
import json
import os
import pickle
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common259 import DAY, OUT, T0, T1  # noqa: E402

RX = re.compile(r"#(\S+) Liquidated (Long|Short): \$([0-9.]+)([KMB]?) at \$([0-9.]+)")
MUL = {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}
EDGES = [2.3e6, 5.3e6, 12.4e6, 41.5e6]


def load():
    rows = []
    for ln in open("s72/liq.jsonl"):
        i, t, txt = json.loads(ln)
        m = RX.search(txt)
        if m:
            rows.append((pd.Timestamp(t).timestamp(), m.group(1), m.group(2), float(m.group(3)) * MUL[m.group(4)]))
    L = pd.DataFrame(rows, columns=["t", "s", "side", "usd"])
    return L[(L.t >= T0) & (L.t < T1)]


def daily():
    """Монето-сутки вселенной: оборот перпа за сутки, без спота, пятая доля оборота (по обороту за 7 сут)."""
    K = pickle.load(open("s2/k2y.pkl", "rb"))
    U = json.load(open(f"{OUT}/universe.json"))
    rows = []
    for s, u in U.items():
        a = K[s]
        d = (a["t"] // DAY) * DAY
        v = pd.Series(a["qv"].astype(float)).groupby(d).sum()
        v = v[(v.index >= max(T0, u["live0"])) & (v.index < min(T1, u["live1"]))]
        to7 = v.rolling(7, min_periods=1).mean().shift(1).fillna(v)
        s0 = u["spot0"] or np.inf
        rows.append(pd.DataFrame({"s": s, "d": v.index, "qv": v.values, "to7": to7.values, "ns": v.index + DAY <= s0}))
    D = pd.concat(rows, ignore_index=True)
    D["bk"] = np.searchsorted(EDGES, D.to7.values)
    return D


def cascades(L):
    """Каскад: ликвидации одной стороны у монеты с разрывом < 60 мин; ≥ 3 сообщений или ≥ 0,5 млн $."""
    out = []
    for (s, side), g in L.sort_values("t").groupby(["s", "side"]):
        t = g.t.values; u = g.usd.values
        br = np.r_[0, np.flatnonzero(np.diff(t) > 3600) + 1, len(t)]
        for a, b in zip(br[:-1], br[1:]):
            n, usd = b - a, u[a:b].sum()
            if n >= 3 or usd >= 5e5:
                out.append((s, side, t[a], t[b - 1], n, usd))
    return pd.DataFrame(out, columns=["s", "side", "t0", "t1", "n", "usd"])


def main():
    L = load()
    D = daily()
    L["d"] = (L.t // DAY) * DAY
    L = L.merge(D[["s", "d", "ns", "bk", "qv"]], on=["s", "d"], how="inner")
    C = cascades(L)
    C["d"] = (C.t0 // DAY) * DAY
    C = C.merge(D[["s", "d", "ns", "bk"]], on=["s", "d"], how="inner")
    print(f"сообщений о ликвидациях в окне 10.2024–10.2026 у перпов вселенной: {len(L):,}; каскадов: {len(C):,}")
    for nm, sel in (("все", lambda x: np.ones(len(x), bool)),) + tuple((f"оборот {b + 1}", (lambda x, b=b: x.bk.values == b)) for b in range(5)):
        for ns in (True, False):
            d = D[(D.ns == ns) & sel(D)]
            x = L[(L.ns == ns) & sel(L)]
            c = C[(C.ns == ns) & sel(C)]
            cd = len(d)
            if not cd:
                continue
            sh = x[x.side == "Short"].usd.sum() / max(x.usd.sum(), 1)
            cs = c[c.side == "Short"]
            print(f"  {nm}, {'без спота' if ns else 'со спотом'}: монето-суток {cd:,}; ликвидаций {len(x) / cd * 100:.1f} на 100 "
                  f"монето-суток, {x.usd.sum() / max(d.qv.sum(), 1) * 1e4:.1f} $ на 10 тыс. $ оборота; доля шортов в $ {sh:.0%}; "
                  f"каскадов {len(c) / cd * 100:.2f} на 100 монето-суток (шортов {len(cs) / max(len(c), 1):.0%}), "
                  f"монето-суток с каскадом {c.groupby(['s', 'd']).ngroups / cd:.1%}")
    # каскады возле пампов и обвалов (±2 ч от закрытия свечи события)
    E = pd.read_pickle(f"{OUT}/events.pkl")
    for kind, side in (("pump", "Short"), ("dump", "Long")):
        for ns in (True, False):
            e = E[(E.kind == kind) & (E.nospot == ns)]
            c = C[(C.side == side) & (C.ns == ns)]
            idx = {s: g.t0.values for s, g in c.groupby("s")}
            hit = [len(idx.get(r.p, [])) and (np.abs(idx[r.p] - r.t) <= 7200).any() for r in e.itertuples()]
            print(f"  {kind} {'без спота' if ns else 'со спотом'}: событий {len(e)}, с каскадом {side} в ±2 ч — {np.mean(hit):.0%}")
    C.to_pickle(f"{OUT}/liq_cascades.pkl")


if __name__ == "__main__":
    main()
