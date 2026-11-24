"""s271 Г3 — частота «разгрузки после пампа перпа»: памп как у 🇰🇷/🛒 (+15% от спокойной базы за ≤ 2 ч, `s15/kr_panel.pumps`,
не чаще раза в сутки), который ведёт перп: доля спота Binance в обороте последнего полного часа < 10% или спота нет
(2022–2024 гг.: только «спота нет», доли спота за те годы нет). Триггер — первая 15-мин свеча в 6 ч после свечи пампа, где
продажи тейкеров перевешивают (tb/qv ≤ 0,45), закрытие ниже минимума прошлой свечи и цена ещё ≥ +8% к базе. Доходы не
считаются. Запуск из /home/user/mc_data."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common271 import BAR, H, PER, base, crypto_perps, fmt, freq_line, load_k, spot_start  # noqa: E402


def pumps(a):
    """Как s15/kr_panel.pumps: индексы свечей, где впервые достигнуто +15% от спокойной базы за ≤ 8 свечей; раз в сутки."""
    c, h = a["c"].astype(float), a["h"].astype(float)
    n = len(c)
    calm = np.zeros(n, bool)
    calm[8:] = np.abs(c[8:] / np.where(c[:-8] > 0, c[:-8], np.nan) - 1) <= 0.05
    hit = np.zeros(n, bool)
    hs = pd.Series(h)
    for L in range(1, 9):
        mx = hs.rolling(L, min_periods=L).max().values
        b = np.r_[np.full(L, np.nan), c[:-L]]
        cb = np.r_[np.zeros(L, bool), calm[:-L]]
        hit |= cb & (mx >= b * 1.15) & (np.arange(n) - L >= 8)
    nz = np.flatnonzero(a["qv"] > 0)
    if not len(nz):
        return np.array([], dtype=np.int64)
    hit &= (np.arange(n) >= nz[0] + 96) & (np.arange(n) <= nz[-1]) & (a["qv"] > 0)
    out, last = [], -10 ** 9
    for j in np.flatnonzero(hit):
        if j - last >= 96:
            out.append(int(j)); last = j
    return np.array(out, dtype=np.int64)


def run(per):
    cfg = PER[per]
    K = load_k(per)
    P = crypto_perps(K)
    ss = spot_start(P)
    SP = pickle.load(open("s23/spot1h.pkl", "rb")) if per == "2024–2026" else {}
    allp, perp_led, trig_all, trig_perp, nospot, delay = [], [], [], [], [], []
    for p in P:
        a = K[p]
        J = pumps(a)
        if not len(J):
            continue
        t = a["t"].astype(np.int64); c = a["c"].astype(float); lo = a["l"].astype(float)
        q = a["qv"].astype(float); tb = a["tb"].astype(float)
        sp = SP.get(p) if p in SP else SP.get(base(p))
        st = sp[:, 0].astype(np.int64) if sp is not None and len(sp) else None
        s0 = ss.get(p)
        for j in J:
            te = int(t[j]) + BAR
            hend = te // H * H
            if s0 is None or s0 > te:
                share, nos = 0.0, True
            elif st is not None:
                k = np.searchsorted(st, hend - H)
                if k < len(st) and st[k] == hend - H:
                    pv = q[(t >= hend - H) & (t < hend)].sum()
                    sv = float(sp[k, 1])
                    share = sv / (sv + pv) if sv + pv > 0 else np.nan
                else:
                    share = np.nan
                nos = False
            else:
                share, nos = np.nan, False          # спот был, но доли за эти годы нет
            led = nos or (np.isfinite(share) and share < 0.10)
            allp.append(te)
            if led:
                perp_led.append(te)
            if nos:
                nospot.append(te)
            b = np.nanmin(c[max(0, j - 8):j]) if j >= 1 else c[j]
            for k in range(j + 1, min(j + 25, len(c))):
                if q[k] <= 0 or t[k] != t[j] + (k - j) * BAR:
                    break
                if tb[k] / q[k] <= 0.45 and c[k] < lo[k - 1] and c[k] >= b * 1.08:
                    trig_all.append(int(t[k]) + BAR)
                    if led:
                        trig_perp.append(int(t[k]) + BAR)
                        delay.append((k - j) * 15)
                    break
    a0, a1, mid, tbb = cfg["t0"], cfg["t1"], cfg["mid"], cfg["tb"]
    print(f"\n== {per}")
    print("пампы все:               ", fmt(freq_line(allp, a0, a1, mid, tbb)))
    print("пампы без спота Binance: ", fmt(freq_line(nospot, a0, a1, mid, tbb)))
    print("пампы, которые ведёт перп:", fmt(freq_line(perp_led, a0, a1, mid, tbb)))
    print("триггер разгрузки, все пампы:   ", fmt(freq_line(trig_all, a0, a1, mid, tbb)))
    print("триггер разгрузки, ведёт перп:  ", fmt(freq_line(trig_perp, a0, a1, mid, tbb)))
    if delay:
        q = np.percentile(delay, [25, 50, 75])
        print(f"задержка триггера после свечи пампа (ведёт перп), мин: квартили {q[0]:.0f} / {q[1]:.0f} / {q[2]:.0f}; "
              f"доля пампов перпа с триггером {len(trig_perp) / max(len(perp_led), 1):.0%}")


if __name__ == "__main__":
    for per in PER:
        run(per)
