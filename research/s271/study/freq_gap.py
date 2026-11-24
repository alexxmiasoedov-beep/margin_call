"""s271 Г2 — частота «разрыва перп–спот Binance» на отметке часа (2024–2026 гг.; спот `s23/spot1h.pkl` по 18.10.2026):
g = закрытие перпа на отметке часа T / закрытие спота Binance той же монеты на T − 1 ≤ −1% (перп дешевле) или ≥ +1%;
«внезапно» — медиана |g| за прошлые 4 часа ≤ 0,3%; перп старше 7 сут, оборот спота за час ≥ 50 тыс. $; первое у монеты
и стороны за 24 ч. Это проверка премии `s12/prem.pkl` по последним ценам: премия Binance считается по ценам «удара»
(impact bid/ask) и у тонких стаканов уходит в минус без разрыва цен. Доходы не считаются. Запуск из /home/user/mc_data."""
import os
import pickle
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common271 import DAY, H, PER, base, cooldown, crypto_perps, fmt, freq_line, hourly_close, live_idx, load_k  # noqa: E402


def main():
    per = "2024–2026"
    cfg = PER[per]
    K = load_k(per)
    P = crypto_perps(K)
    SP = pickle.load(open("s23/spot1h.pkl", "rb"))
    res = {}
    n_h = 0
    for p in P:
        sp = SP.get(p) if p in SP else SP.get(base(p))
        if sp is None or not len(sp):
            continue
        i0, _ = live_idx(K[p])
        if i0 is None:
            continue
        t_live = int(K[p]["t"][i0])
        T, px, _ = hourly_close(K[p])
        st = sp[:, 0].astype(np.int64) + H                    # время закрытия часа спота
        k = np.searchsorted(st, T)
        k2 = np.minimum(k, len(st) - 1)
        hit = (k < len(st)) & (st[k2] == T)
        T, px, k2 = T[hit], px[hit], k2[hit]
        sc = sp[k2, 4].astype(float); sv = sp[k2, 1].astype(float)
        ok = (sc > 0) & (px > 0) & (sv >= 5e4) & (T - t_live >= 7 * DAY)
        if not ok.any():
            continue
        mult = 10.0 ** np.round(np.log10(np.nanmedian(px[ok] / sc[ok])))   # 1000PEPE: спот BONK/PEPE без множителя
        g = np.where(ok, px / (sc * mult) - 1, np.nan)
        med = np.full(len(g), np.nan)
        if len(g) > 4:
            w = np.lib.stride_tricks.sliding_window_view(np.abs(g), 4)[:-1]
            med[4:] = np.nanmedian(w, axis=1)
        n_h += int(ok.sum())
        for thr in (0.01, 0.02):
            for side in (-1, 1):
                for kind, cond in (("уровень", ok), ("внезапно", ok & (med <= 0.003))):
                    m = cond & (side * g >= thr)
                    Tm = T[m]
                    Tm = Tm[cooldown(Tm, DAY)]
                    res.setdefault((thr, side, kind), []).extend(Tm.tolist())
    print(f"== {per}: монето-часов с перпом и спотом {n_h}")
    for (thr, side, kind), Tm in sorted(res.items()):
        print(f"перп/спот {'≤ −' if side < 0 else '≥ +'}{thr:.0%}, {kind}: {fmt(freq_line(Tm, cfg['t0'], cfg['t1'], cfg['mid']))}")


if __name__ == "__main__":
    main()
