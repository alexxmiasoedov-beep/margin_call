"""s181 — разлоки по расписанию В казну/фонд проекта (DefiLlama emissions, кэш s139/ll: категория noncirculating —
Treasury, Foundation, Ecosystem, Reserve…), которые журналы 🔑 и 🔑⁺ исключают. После такого разлока у казны
появляются свободные токены для продажи по своему усмотрению. Доля — к монетам в обращении по расписанию без
noncirculating (как в s139/unlock_test.events), разовые (cliff) события одних суток складываются. Частота в месяц
по периодам (перп жив), пересечение с событиями 🔑⁺ (любой разлок ≥ 1% вне казны в ±3 сут). Только частоты."""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common181 as C  # noqa: E402
import treasury_outflows as T  # noqa: E402

DAY = 86400
LL = f"{C.D}/s139/ll"


def events(cat_set):
    M = pd.read_pickle(f"{C.D}/s139/map.pkl").set_index("slug")
    rows = []
    for f in sorted(glob.glob(f"{LL}/e_*.json")):
        slug = os.path.basename(f)[2:-5]
        if slug not in M.index or not isinstance(M.at[slug, "fut"], str):
            continue
        try:
            E = json.load(open(f))
        except Exception:
            continue
        nonc = set((E.get("categories") or {}).get("noncirculating", []))
        ser = []
        for sec in (E.get("documentedData") or {}).get("data") or []:
            if sec.get("label") in nonc or not sec.get("data"):
                continue
            d = pd.DataFrame(sec["data"])
            if "timestamp" not in d or "unlocked" not in d:
                continue
            ser.append(pd.Series(d.unlocked.astype(float).values, index=d.timestamp.astype(float).astype(np.int64)))
        if not ser:
            continue
        circ = pd.concat(ser, axis=1).sort_index().ffill().fillna(0).sum(axis=1)
        agg = {}
        for ev in (E.get("metadata") or {}).get("events") or []:
            if ev.get("unlockType") != "cliff" or ev.get("category") not in cat_set:
                continue
            try:
                t = int(float(ev["timestamp"])); n = float(sum(ev.get("noOfTokens") or [0]))
            except Exception:
                continue
            if n <= 0:
                continue
            k = t // DAY
            agg[k] = (min(agg.get(k, (t, 0))[0], t), agg.get(k, (t, 0))[1] + n)
        for _, (t, n) in agg.items():
            before = circ[circ.index <= t - DAY]
            c0 = float(before.iloc[-1]) if len(before) else 0.0
            if c0 > 0:
                rows.append(dict(slug=slug, perp=M.at[slug, "fut"], t=t, share=n / c0))
    return pd.DataFrame(rows)


def main():
    P = C.perps()
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "s139"))
    import unlock_test as U  # noqa: E402
    K = U.events()
    K["day"] = K["T"] // DAY
    K = K.groupby(["key", "day"]).share.sum().reset_index()
    K = K[K.share >= 0.01]
    for lab, cs in (("казна/фонд (noncirculating)", {"noncirculating"}), ("экосистема (ecosystem)", {"ecosystem"})):
        E = events(cs)
        E = E[E.perp.map(lambda p: p in P and True) & np.array([C.alive(P[p], t) if p in P else False
                                                                 for p, t in zip(E.perp, E.t)], bool)]
        print(f"\n{lab}: разовых разлоков с живым перпом {len(E)}, проектов {E.slug.nunique()}")
        for thr in (0.005, 0.01, 0.05):
            z = T.one_per(E[E.share >= thr], "perp", 7 * DAY)
            day = z.t // DAY
            ov = np.array([bool(len(K[(K.key == p) & (K.day >= d - 3) & (K.day <= d + 3)])) for p, d in zip(z.perp, day)])
            print(f"  ≥ {thr:.1%}: в месяц " + " / ".join(f"{C.month_counts(z.t, p):5.2f}" for p in C.PER) +
                  f"  (всего {len(z)}; вместе с разлоком 🔑⁺ ≥ 1% в ±3 сут — {ov.mean():.0%}; "
                  f"без него " + " / ".join(f"{C.month_counts(z.t[~ov], p):5.2f}" for p in C.PER) + ")")
        print("  проекты (≥ 1%):", E[E.share >= 0.01].groupby("slug").size().sort_values(ascending=False).head(12).to_dict())


if __name__ == "__main__":
    main()
