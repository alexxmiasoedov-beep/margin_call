"""s186 — дневной оборот перпов Gate USDT-M (площадка, где хеджируются токены Gate) для базовых активов токенов Gate.

Gate /futures/usdt/candlesticks 1d (поле sum — оборот в USDT), от сегодня назад кусками по 999 сут до 01.01.2020.
Нужен для доли потока ребаланса в обороте той площадки, где он исполняется. Итог: /home/user/mc_data/s186/gate_perp_daily.pkl;
лог — gate_perp.log. Доходы не считаются."""
import json
import os
import pickle
import re
import time

import numpy as np
import pandas as pd

import common186 as C

L = C.Log("gate_perp")
GATE = "https://api.gateio.ws/api/v4"


def main():
    pairs = json.load(open(f"{C.RAW}/gate_pairs.json"))
    unds = sorted({C.LT_RE.match(p["base"]).group(1) for p in pairs
                   if C.LT_RE.match(p["base"]) and p["quote"] == "USDT" and re.search(r"Long|Short", p.get("base_name", ""))})
    path = f"{C.OUT}/gate_perp_daily.pkl"
    out = pickle.load(open(path, "rb")) if os.path.exists(path) else {}
    for u in unds:
        if u in out:
            continue
        rows = []
        t1 = int(time.time()) // C.DAY * C.DAY
        while t1 > 1577836800:
            t0 = max(t1 - 999 * C.DAY, 1577836800)
            d = C.jget(f"{GATE}/futures/usdt/candlesticks?contract={u}_USDT&interval=1d&from={t0}&to={t1}")
            time.sleep(0.12)
            if not isinstance(d, list) or not d:
                break
            rows += [(int(x["t"]), float(x.get("sum") or 0), float(x["c"])) for x in d]
            if int(d[0]["t"]) > t0 + C.DAY:
                break
            t1 = t0 - C.DAY
        if rows:
            a = np.array(sorted(set(rows)))
            out[u] = pd.DataFrame({"qv": a[:, 1], "c": a[:, 2]}, index=a[:, 0].astype(np.int64))
        else:
            out[u] = None
        if len(out) % 25 == 0:
            pickle.dump(out, open(path, "wb"))
    pickle.dump(out, open(path, "wb"))
    ok = {u: df for u, df in out.items() if df is not None and len(df)}
    L("базовых активов токенов Gate:", len(unds), "с перпом Gate USDT-M:", len(ok))
    fy = pd.Series({u: pd.Timestamp(int(df.index.min()), unit="s").year for u, df in ok.items()}).value_counts().sort_index()
    L("год первой свечи перпа Gate:", fy.to_dict())


if __name__ == "__main__":
    main()
