"""s271 Г2 (по премии Binance) — частота «отрыва перпа от индекса у монет со спотом Binance»: премия перпа к индексу на закрытии 15-мин свечи
(premiumIndexKlines, `s12/prem.pkl`, 10.2024–18.10.2026) ≤ −0,5 / −1% (перп дешевле спота) или ≥ +0,5 / +1%; спот Binance
к этому моменту есть (`spot_start`), перп старше 7 сут; первое у монеты и стороны за 24 ч. «Внезапно» — медиана премии
за прошлые 4 ч по модулю ≤ 0,3% (не хронический дисконт у пола фандинга). Для сравнения — перпы без спота.
Доходы не считаются. Запуск из /home/user/mc_data."""
import os
import pickle
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common271 import BAR, DAY, PER, cooldown, crypto_perps, fmt, freq_line, live_idx, load_k, spot_start  # noqa: E402


def main():
    per = "2024–2026"
    cfg = PER[per]
    K = load_k(per)
    P = crypto_perps(K)
    ss = spot_start(P)
    PR = pickle.load(open("s12/prem.pkl", "rb"))
    res = {}
    for p in P:
        if p not in PR:
            continue
        i0, _ = live_idx(K[p])
        if i0 is None:
            continue
        t_live = int(K[p]["t"][i0])
        pt, pv = PR[p]
        te = pt.astype(np.int64) + BAR
        ok = (te - t_live >= 7 * DAY) & np.isfinite(pv)
        s0 = ss.get(p)
        spot = np.array([s0 is not None and s0 <= x for x in te]) if s0 is not None else np.zeros(len(te), bool)
        # «внезапный» отрыв: медиана премии за прошлые 4 ч (16 свечей) по модулю ≤ 0,3%
        med = np.full(len(pv), np.nan)
        if len(pv) > 16:
            w = np.lib.stride_tricks.sliding_window_view(pv.astype(float), 16)[:-1]
            med[16:] = np.median(w, axis=1)
        calm = np.abs(med) <= 0.003
        for thr in (0.005, 0.01, 0.02):
            for side in (-1, 1):
                for kind, cond in (("уровень", ok), ("внезапно", ok & calm)):
                    m = cond & (side * pv >= thr)
                    for grp, g in (("со спотом", spot), ("без спота", ~spot)):
                        T = te[m & g]
                        T = T[cooldown(T, DAY)]
                        res.setdefault((thr, side, kind, grp), []).extend(T.tolist())
    for (thr, side, kind, grp), T in sorted(res.items()):
        print(f"премия {'≤ −' if side < 0 else '≥ +'}{thr:.1%}, {kind}, {grp}: {fmt(freq_line(T, cfg['t0'], cfg['t1'], cfg['mid']))}")


if __name__ == "__main__":
    main()
