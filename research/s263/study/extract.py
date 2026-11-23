"""s263 — выборка TradFi-перпов из общих свечей и фандинга s224 (k_d.pkl, fund_d.pkl) в память (/dev/shm/s263).
Справочник контрактов — снимок exchangeInfo 23.11.2026 (s252/exinfo.json): contractType TRADIFI_PERPETUAL, котировка USDT.
Для сравнения берутся и криптоперпы BTC, ETH, PAXG, XAUT.

Запуск из /home/user/mc_data: python3 -I <путь>/extract.py
Выход: /dev/shm/s263/tf_k.pkl (символ → массивы 15-мин свечей, только свечи с оборотом > 0 помечены в qv),
       /dev/shm/s263/tf_f.pkl (символ → [время, интервал, ставка]), s263/tf_meta.csv (справочник)."""
import datetime
import json
import os
import pickle

import numpy as np
import pandas as pd

SHM = "/dev/shm/s263"
UTC = datetime.timezone.utc
REF = ["BTC", "ETH", "PAXG", "XAUT"]


def main():
    os.makedirs(SHM, exist_ok=True)
    ex = json.load(open("s252/exinfo.json"))
    rows = []
    for s in ex["symbols"]:
        if s.get("contractType") != "TRADIFI_PERPETUAL" or s.get("quoteAsset") != "USDT":
            continue
        rows.append(dict(sym=s["symbol"][:-4], symbol=s["symbol"], ut=s["underlyingType"],
                         sub=",".join(s.get("underlyingSubType") or []), status=s["status"],
                         onboard=int(s["onboardDate"]) // 1000, mmr=float(s["maintMarginPercent"]),
                         imr=float(s["requiredMarginPercent"]), take_bound=float(s.get("marketTakeBound") or "nan")))
    meta = pd.DataFrame(rows).sort_values(["ut", "sym"]).reset_index(drop=True)
    K = pickle.load(open("s224/k_d.pkl", "rb"))
    keep = [s for s in list(meta.sym) + REF if s in K]
    miss = [s for s in meta.sym if s not in K]
    out = {s: {f: np.asarray(v) for f, v in K[s].items()} for s in keep}
    del K
    pickle.dump(out, open(f"{SHM}/tf_k.pkl", "wb"), protocol=4)
    F = pickle.load(open("s224/fund_d.pkl", "rb"))
    fo = {s: np.asarray(F[s]) for s in keep if s in F}
    del F
    pickle.dump(fo, open(f"{SHM}/tf_f.pkl", "wb"), protocol=4)
    first, last, nvol = [], [], []
    for s in meta.sym:
        if s in out:
            a = out[s]; v = a["qv"] > 0
            first.append(int(a["t"][v][0]) if v.any() else np.nan)
            last.append(int(a["t"][v][-1]) if v.any() else np.nan)
            nvol.append(int(v.sum()))
        else:
            first.append(np.nan); last.append(np.nan); nvol.append(0)
    meta["k_first"] = first; meta["k_last"] = last; meta["k_n"] = nvol
    meta["has_f"] = [s in fo for s in meta.sym]
    meta.to_csv("s263/tf_meta.csv", index=False)
    print(f"TradFi USDT в снимке: {len(meta)}; со свечами: {len(meta) - len(miss)}; нет свечей: {miss}")
    print(meta.groupby("ut").agg(n=("sym", "size"), with_k=("k_n", lambda x: int((x > 0).sum()))))
    for s in REF:
        print(s, s in out, s in fo)


if __name__ == "__main__":
    main()
