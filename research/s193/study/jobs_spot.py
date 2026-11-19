"""s193 — спотовая SRS-выборка для частоты гипотезы «продавец запаса на споте»: каждые вторые сутки SRS периода,
20 случайных монет из SRS-монет этих суток (ликвидная вселенная перпов), рынок — спот Binance (пара к USDT; если пары
нет — 404, сутки не считаются). seed 193. Итог — /home/user/mc_data/s193/jobs_spot.pkl."""
import numpy as np
import pandas as pd

D = "/home/user/mc_data/s193"


def main():
    rng = np.random.default_rng(1931)
    J = pd.read_pickle(f"{D}/jobs.pkl")
    have = set(zip(J.mkt, J.s, J.d))
    srs = J[J.tags.str.contains("srs") & (J.mkt == "um")]
    rows = []
    for per, g in srs.groupby("per"):
        days = sorted(g.d.unique())[::2]
        for d in days:
            cand = g[g.d == d].s.values
            for s in rng.choice(cand, size=min(20, len(cand)), replace=False):
                if ("spot", s, int(d)) in have:
                    continue
                rows.append(dict(mkt="spot", s=s, d=int(d), per=per, tags="srs_spot", inj=0))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{D}/jobs_spot.pkl")
    print("заданий:", len(X), X.groupby("per").size().to_dict())


if __name__ == "__main__":
    main()
