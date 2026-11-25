"""s288: список перпов Binance USDT-M и даты их жизни по свечам трёх периодов (для доли монет канала с перпом).
Запуск из /home/user/mc_data: python3 -I <repo>/research/s288/study/perps.py → s288/perps.json
{база: [первая свеча с оборотом, последняя, [имена перпов]]}. База — без множителя (1000PEPE → PEPE)."""
import json
import os
import pickle
import re
import sys

import numpy as np

FILES = ["s117/k_2020.pkl", "s117/k_oos.pkl", "s2/k2y.pkl", "s224/k_d.pkl"]


def base(fs):
    m = re.match(r"^(1000000|100000|10000|1000|1M)(.+)$", fs)
    return m.group(2) if m and not m.group(2)[0].isdigit() else fs


def main():
    out = {}
    for f in FILES:
        if not os.path.exists(f):
            print("нет", f); continue
        K = pickle.load(open(f, "rb"))
        for p, a in K.items():
            qv = np.asarray(a["qv"])
            nz = np.flatnonzero(qv > 0)
            if not len(nz):
                continue
            t = np.asarray(a["t"], np.int64)
            b = base(p)
            lo, hi = int(t[nz[0]]), int(t[nz[-1]])
            if b in out:
                out[b][0] = min(out[b][0], lo); out[b][1] = max(out[b][1], hi)
                if p not in out[b][2]:
                    out[b][2].append(p)
            else:
                out[b] = [lo, hi, [p]]
        print(f, len(K), "баз всего", len(out), flush=True)
        del K
    os.makedirs("s288", exist_ok=True)
    json.dump(out, open("s288/perps.json", "w"))


if __name__ == "__main__":
    main()
