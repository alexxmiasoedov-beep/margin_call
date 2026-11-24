"""s278 — сохранить новые данные компактно в /home/user/mc_data/s278 (лимит папки — 100 МБ).

venues_<период>.npz: P — перпы сетки (порядок строк), t0 — начало первого часа (UTC, с), и по площадке массив
«перп × час» log1p(оборот площадки за час в $) в float16 (NaN — пары нет или вне её истории). Сетка — как в panel278:
P1 01.10.2024–18.10.2026, P0 01.10.2022–01.10.2024, PF 04–19.11.2026. Оборот: np.expm1(x.astype(float)).
Сохраняются только площадки, собранные в s278 (остальные лежат в своих папках: s15, s23, s46, s67, s68, s75, s88, s93).
Запуск из /home/user/mc_data: python3 -I <repo>/research/s278/study/save_data.py"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from panel278 import OUT, PER, TMP, perp_hourly  # noqa: E402

NEW = {"P1": ["okx", "bitget", "kucoin", "gate", "htx", "bitbank", "gmo"],
       "P0": ["okx", "bitget", "kucoin", "binance_spot"],
       "PF": ["okx", "bitget", "kucoin", "gate", "htx", "mexc"]}


def main():
    for per, vens in NEW.items():
        P, C, Q, F = perp_hourly(per)
        arrs = {}
        for v in vens:
            f = f"{TMP}/venue_{per}_{v}.npz"
            if not os.path.exists(f):
                continue
            V = np.load(f)["V"].astype(np.float64)
            arrs[v] = np.where(np.isfinite(V), np.log1p(np.maximum(V, 0)), np.nan).astype(np.float16)
        if not arrs:
            continue
        out = f"{OUT}/venues_{per}.npz"
        np.savez_compressed(out, P=np.array(P), t0=np.int64(PER[per]["t0"]), **arrs)
        print(per, sorted(arrs), f"{os.path.getsize(out) / 1e6:.1f} МБ", flush=True)


if __name__ == "__main__":
    main()
