"""s223 — исходы с хеджем индексом альтов для наблюдений s216 (метод — ВЫВОДЫ.md, записан до расчёта).

Берёт s216_feat.pkl (37 признаков и исходы без хеджа) и добавляет 8 исходов с хеджем на фактический срок сделки:
y_hs4, y_hs24, y_hs48, y_hs168 — шорт + ход индекса альтов s103; y_hl4 … y_hl168 — лонг − ход индекса. Сроки и стопы — как
в s216: 4 ч / 10%, 24 ч / 25%, 48 ч / 25%, 7 сут / 50%. Вход на закрытии T, комиссия и фандинг (s187/fastbt.trades).
Для честных сделок комитета — время выхода каждой сделки: u_e_<исход>. Итог — s223_feat.pkl.
Запуск из /home/user/mc_data: python3 <repo>/research/s223/features.py
Окружение (s224): IN и OUT — файлы входа и итога (по умолчанию s216_feat.pkl и s223_feat.pkl)."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
import fastbt as FB  # noqa: E402
from fastbt import K, live  # noqa: E402

DAY = 86400
OUTS = {"hs4": (-1, 0.10, 4), "hs24": (-1, 0.25, 24), "hs48": (-1, 0.25, 48), "hs168": (-1, 0.50, 168),
        "hl4": (1, 0.10, 4), "hl24": (1, 0.25, 24), "hl48": (1, 0.25, 48), "hl168": (1, 0.50, 168)}


def main():
    D = pd.read_pickle(os.environ.get("IN", "s216_feat.pkl")).sort_values(["T", "s"]).reset_index(drop=True)
    for k in OUTS:
        D[f"y_{k}"] = np.nan; D[f"u_e_{k}"] = np.nan
    for s, idx in D.groupby("s").groups.items():
        if s not in K:
            continue
        t = K[s]["t"].astype(np.int64)
        pos = np.asarray(idx)
        st = D.loc[idx, "T"].to_numpy(np.int64) - 900
        I = np.searchsorted(t, st)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == st)
        lo, _ = live(s)
        ok &= t[np.minimum(I, len(t) - 1)] >= lo + DAY
        if not ok.any():
            continue
        for k, (side, sl, hold) in OUTS.items():
            okt, net, _, _, tend = FB.trades(s, I[ok], sl, hold, side)
            mv = FB.alt_mv(t[I[ok]] + 900, tend)
            y = np.where(okt, net - side * mv, np.nan)
            D.loc[pos[ok], f"y_{k}"] = y
            D.loc[pos[ok], f"u_e_{k}"] = np.where(okt, tend, np.nan)
    D.to_pickle(os.environ.get("OUT", "s223_feat.pkl"))
    for k in OUTS:
        raw = {"hs": "s", "hl": "l"}[k[:2]] + k[2:]
        print(f"{k}: наблюдений {D[f'y_{k}'].notna().sum()}, среднее с хеджем {D[f'y_{k}'].mean():+.2%}, "
              f"без хеджа {D[raw].mean():+.2%}")


if __name__ == "__main__":
    main()
