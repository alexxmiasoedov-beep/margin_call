"""s42: разбор после проверки (не записанные заранее гипотезы, только чтобы понять результат test.py):
1) рынок альтов вперёд по третям базиса и BVOL — по всем часам, t Ньюи — Уэста;
2) 🇰🇷 и 📢 при высоком и низком базисе по кварталам;
3) Г2 при более низких порогах всплеска. Запуск из папки данных после test.py."""
import pickle
import sys
import os

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test import HOURS, CUT, pct90, spikes, dayt, at, W7  # noqa: E402


def nw_diff(y, x, lag):
    """Разница средних y при x=1 и x=0 (МНК на фиктивной) и t Ньюи — Уэста с лагом lag (ряд по часам)."""
    m = ~np.isnan(y) & ~np.isnan(x)
    y, x = y[m], x[m]
    X = np.c_[np.ones_like(x), x]
    XtXi = np.linalg.inv(X.T @ X)
    b = XtXi @ X.T @ y
    u = (y - X @ b)[:, None] * X
    S = u.T @ u
    for k in range(1, lag + 1):
        w = 1 - k / (lag + 1)
        G = u[k:].T @ u[:-k]
        S += w * (G + G.T)
    V = XtXi @ S @ XtXi
    return b[1], b[1] / np.sqrt(V[1, 1])


def main():
    R = pickle.load(open("s42/res.pkl", "rb"))
    T = pd.read_pickle("s42/trades_feat.pkl")
    GR = pickle.load(open("s22/grid.pkl", "rb"))
    gr = GR["grid"]
    B, BV = R["B"], R["BV"]
    F = {"уровень базиса": pct90(B["MKT"]), "уровень BVOL": pct90(BV),
         "изменение базиса за 7 сут": pct90(B["MKT"] - B["MKT"].shift(W7)),
         "изменение BVOL за 7 сут": pct90(BV / BV.shift(W7) - 1)}
    print("1) Рынок альтов (медиана фьючерсов) вперёд: верхняя треть против нижней, все часы 10.2024–10.2026")
    for name, s in F.items():
        p = at(s, gr)
        for h in (24, 72, 168):
            y = GR["MK"][h].astype(float)
            sel = (p >= 2 / 3) | (p < 1 / 3)
            x = np.where(p >= 2 / 3, 1.0, 0.0)
            out = []
            for hm in (np.ones_like(sel), gr < CUT, gr >= CUT):
                mm = sel & hm.astype(bool) & ~np.isnan(y)
                d, t = nw_diff(y[mm], x[mm], h)
                out.append(f"{d:+.2%} (t {t:+.1f})")
            print(f"   {name:26s} {h // 24} сут: верх − низ {out[0]} | половины {out[1]} / {out[2]}")

    print("\n2) Сделки 🇰🇷 и 📢 по кварталам: верхняя треть базиса / нижняя (n, средний доход)")
    T["q"] = pd.to_datetime(T.te, unit="s").dt.to_period("Q").astype(str)
    for j in ("🇰🇷", "📢", "канал", "🏦"):
        g = T[T.journal == j]
        rows = []
        for q, gg in g.groupby("q"):
            a, b = gg[gg.bs_lvl >= 2 / 3], gg[gg.bs_lvl < 1 / 3]
            rows.append(f"{q}: {len(a)}/{len(b)} {a.net.mean():+.1%}/{b.net.mean():+.1%}")
        print(f"   {j}: " + " | ".join(rows))

    print("\n3) Г2 при других порогах всплеска BVOL за 24 ч (одно событие за 3 сут)")
    for thr in (0.20, 0.15, 0.10):
        ev, _ = spikes(BV, thr)
        ev = ev[ev >= gr[0]]
        k = np.searchsorted(gr, ev); k = k[k < len(gr)]
        ok = (gr >= ev.min()) & (gr <= T.te.max())
        mk = GR["MK"][168]; e = mk[k]
        j = np.searchsorted(ev, T.te.values, side="right") - 1
        post = (j >= 0) & (T.te.values - ev[np.clip(j, 0, None)] <= 72 * 3600)
        a, b = T[post], T[~post]
        d, t, tw = dayt(a.set_index("te").net, b.set_index("te").net)
        kr = T.journal == "🇰🇷"
        dk, tk, twk = dayt(T[post & kr].set_index("te").net, T[~post & kr].set_index("te").net)
        print(f"   ≥ {thr:.0%}: {len(ev)} всплесков | рынок за 7 сут {np.nanmean(e) - np.nanmean(mk[ok]):+.2%} к обычному"
              f" | сделки после всплеска {post.sum()}: разница {d:+.2%} (t {t:+.1f}) | 🇰🇷 {dk:+.2%} (t {tk:+.1f}, {(post & kr).sum()})")


if __name__ == "__main__":
    main()
