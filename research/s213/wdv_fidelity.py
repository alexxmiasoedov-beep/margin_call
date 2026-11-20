"""s213 — сверка двойника 🐋ᵛ: λ бота (scanner._wdv_lambda по 15-мин свечам в формате Binance) против λ исследования
(run.py: сумма оборота 672 свечей архива перед свечой входа / 7) на всех событиях 🐋 периода; решение λ ≥ 0,05.

Запуск из /home/user/mc_data (BOT_DIR — папка bot с новой версией бота, по умолчанию ../../bot от этого файла):
  python3 wdv_fidelity.py 2024–2026
  MC_K=s117/k_oos.pkl MC_F=s117/fund_oos.pkl python3 wdv_fidelity.py 2022–2024
  MC_K=s117/k_2020.pkl MC_F=s117/fund_2020.pkl python3 wdv_fidelity.py 2020–2022
"""
import os
import sys
import tempfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
os.environ.setdefault("STATE_FILE", os.path.join(tempfile.mkdtemp(), "state.json"))
sys.path.insert(0, os.environ.get("BOT_DIR") or os.path.join(HERE, "..", "..", "bot"))
import scanner  # noqa: E402

OUT = "/home/user/mc_data"


def main(per):
    import fastbt as FB  # noqa: E402
    K = FB.K
    R = pd.read_pickle(f"{OUT}/s213_main_{per}.pkl")
    R = R[R.net.notna() & (R.r24.abs() <= 0.05)]
    rows = []
    for r in R.itertuples():
        t = K[r.perp]["t"].astype(np.int64)
        I = int(np.searchsorted(t, r.entry - 900))
        a = max(0, I - scanner.WDV_K + 2)                      # как ответ Binance: до WDV_K свечей, последняя — свеча входа
        k = [[int(t[i]) * 1000, 0, 0, 0, float(K[r.perp]["c"][i]), 0, int(t[i]) * 1000 + 899999, float(K[r.perp]["qv"][i])]
             for i in range(a, I + 1)]
        lam = scanner._wdv_lambda(k, r.amt, r.perp)
        rows.append((r.perp, r.entry, r.lam, lam[0] if lam else np.nan))
    X = pd.DataFrame(rows, columns=["perp", "t", "lam_bt", "lam_bot"])
    both = X.lam_bt.notna() & X.lam_bot.notna()
    rel = (X.lam_bot[both] / X.lam_bt[both] - 1).abs()
    d_bt, d_bot = X.lam_bt >= scanner.WDV_LAM, X.lam_bot >= scanner.WDV_LAM
    print(f"{per}: событий 🐋 {len(X)}; λ есть у бэктеста {int(X.lam_bt.notna().sum())}, у бота {int(X.lam_bot.notna().sum())}; "
          f"расхождение λ больше 0,1%: {int((rel > 1e-3).sum())}")
    print(f"  решение λ ≥ {scanner.WDV_LAM:g}: бэктест {int(d_bt.sum())}, бот {int(d_bot.sum())}, совпало {int((d_bt == d_bot).sum())} "
          f"из {len(X)}")
    bad = X[d_bt != d_bot]
    if len(bad):
        print("  расхождения:\n" + bad.assign(t=pd.to_datetime(bad.t, unit="s")).to_string())


if __name__ == "__main__":
    main(sys.argv[1])
