"""s288 — склад Tether: после авторизации (чеканка USDT в Tether Treasury) — через сколько суток выходы из казны в той же
сети набирают 50% и 100% партии; доля выходов из казны, которые смена сети. Архив Whale Alert, только счёт.
Запуск из /home/user/mc_data: python3 -I <repo>/research/s288/study/tether_inventory.py → s288/tether_inventory.txt"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common288 as C  # noqa: E402

LINES = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LINES.append(s)


def main():
    A = pd.read_pickle(f"{C.OUT}/wa_archive.pkl.gz")
    U = A[A.sym == "USDT"].copy()
    U["y"] = pd.to_datetime(U.tb, unit="s").dt.year
    mint = U[(U.type == "mint") & (U.to == "tether treasury")].sort_values("tb")
    out = U[(U.type == "transfer") & (U.frm == "tether treasury")].sort_values("tb")
    back = U[(U.type == "transfer") & (U.to == "tether treasury")].sort_values("tb")
    say(f"Авторизаций (чеканка USDT в казну): {len(mint)}; выходов из казны: {len(out)}; возвратов в казну: {len(back)}")
    say("по годам и сетям, авторизаций:\n" + pd.crosstab(mint.y, mint.chain).to_string())
    rows = []
    for _, m in mint.iterrows():
        o = out[(out.chain == m.chain) & (out.tb >= m.tb)]
        cs = o.amt.cumsum().values
        tt = o.tb.values
        r = {"y": m.y, "chain": m.chain, "amt": m.amt}
        for k, q in (("d50", 0.5), ("d100", 1.0)):
            j = np.searchsorted(cs, q * m.amt)
            r[k] = (tt[j] - m.tb) / 86400 if j < len(tt) else np.nan
        nxt = mint[(mint.chain == m.chain) & (mint.tb > m.tb)].tb
        r["to_next"] = (nxt.iloc[0] - m.tb) / 86400 if len(nxt) else np.nan
        rows.append(r)
    R = pd.DataFrame(rows)
    say("\nСутки от авторизации до выхода из казны той же сети 50% / 100% партии (медиана, по годам); до следующей авторизации")
    say(R.groupby("y")[["d50", "d100", "to_next"]].median().round(1).to_string())
    say("\nВыходы из казны: какая доля — смена сети (тот же объём ±0,5% вернулся в казну в другой сети за ±24 ч)")
    sw = []
    bt, ba, bc = back.tb.values, back.amt.values, back.chain.values
    for _, o in out.iterrows():
        k = (np.abs(bt - o.tb) <= 86400) & (np.abs(ba / o.amt - 1) <= 0.005) & (bc != o.chain)
        sw.append("смена сети" if k.any() else "выпуск")
    out = out.assign(kind=sw)
    say(pd.crosstab(out.y, out.kind, normalize="index").round(2).to_string())
    say("получатели при смене сети: " + str(out[out.kind == "смена сети"].to.value_counts().head(6).to_dict()))
    open(f"{C.OUT}/tether_inventory.txt", "w").write("\n".join(LINES) + "\n")


if __name__ == "__main__":
    main()
