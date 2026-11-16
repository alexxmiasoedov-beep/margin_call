"""Сверка журнала 🛒 в боте с бэктестом spot_test.py: функция бота scanner.spot_pump_check на всех пампах бэктеста со спотом
Binance. Свечи фьючерса — из s2/k2y.pkl в формате Binance, оборот спота за час — из s23/spot1h.pkl (часовая свеча делится на
четыре 15-мин). Сравниваются доля спота и решение (бот: ≥ 26%, бэктест: ≥ 25,9% — граница третей). Запуск из папки
с данными: python3 <repo>/research/s49/sp_fidelity.py"""
import os
import pickle
import re
import sys
import tempfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["STATE_FILE"] = os.path.join(tempfile.mkdtemp(), "state.json")
sys.path.insert(0, os.path.join(HERE, "..", "..", "bot"))
import scanner  # noqa: E402

K = pickle.load(open("s2/k2y.pkl", "rb"))
SP = pickle.load(open("s23/spot1h.pkl", "rb"))
X = pd.read_pickle("s49/trades.pkl")
X = X[X.spot & X.share.notna()]


def run():
    rows = []
    for r in X.itertuples():
        a = K[r.s]; t = a["t"].astype(np.int64)
        j = int(np.searchsorted(t, r.t - 900))
        k = [[int(t[i]) * 1000, 0, 0, 0, 0, 0, 0, str(float(a["qv"][i]))] for i in range(max(0, j - 12), j + 1)]
        sp = SP[r.s]; spt = sp[:, 0].astype(np.int64)
        coin = re.sub(r"^(1000000|100000|10000|1000)", "", r.s)

        def spot_json(path, timeout=15, sp=sp, spt=spt):
            end = int(path.split("endTime=")[1].split("&")[0]) // 1000 + 1      # = H
            m = np.flatnonzero(spt == end - 3600)
            v = float(sp[m[0], 1]) if len(m) else 0.0
            return [[(end - 3600 + 900 * i) * 1000, 0, 0, 0, 0, 0, 0, str(v / 4)] for i in range(4)]

        scanner.spot_json = spot_json
        ok, why = scanner.spot_pump_check(r.s, coin, int(r.t), k, {f"{coin}USDT": "1"})
        share = float(re.search(r"спот Binance ([\d.]+)%", why).group(1)) / 100
        rows.append(dict(s=r.s, t=r.t, bt=r.share, bot=share, ok_bot=ok, ok_bt=r.share >= 0.259))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    R = run()
    d = (R.bot - R.bt).abs()
    print(f"Пампов со спотом: {len(R)}; расхождение доли: медиана {d.median():.5f}, максимум {d.max():.5f}"
          f" (доля в боте округляется до 0,1%)")
    print(f"Решение совпало: {(R.ok_bot == R.ok_bt).sum()} из {len(R)}; бот вошёл бы в {R.ok_bot.sum()},"
          f" бэктест — {R.ok_bt.sum()}")
    bad = R[R.ok_bot != R.ok_bt]
    if len(bad):
        print("Расхождения (доля бэктеста — бот):")
        for b in bad.head(10).itertuples():
            print(f"  {b.s} {pd.to_datetime(b.t, unit='s')}: {b.bt:.4f} — {b.bot:.4f}")
