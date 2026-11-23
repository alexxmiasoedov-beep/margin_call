"""s259 — события для описания (доходы не считаются): пампы (s15/kr_pumps.pkl: +15% за ≤ 2 ч из покоя, раз в сутки) и обвалы
(зеркало: −15% за ≤ 2 ч из покоя, раз в сутки) всех криптоперпов k2y; метка «без спота на момент».
Итог — /home/user/mc_data/s259/events.pkl (DataFrame: p, j, t, kind, nospot) и список суток для метрик вокруг событий без
спота — s259/met_days.json ({перп: [YYYY-MM-DD, …]}: сутки события −1…+2).
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s259/study/events.py"""
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common259 import BAR, DAY, MID, OUT, T0, T1, load_k  # noqa: E402


def dumps(a):
    """Зеркало s15/kr_panel.pumps: впервые −15% от базы за ≤ 8 свечей, база спокойна (±5% за 2 ч), раз в сутки."""
    c, l = a["c"].astype(float), a["l"].astype(float)
    n = len(c)
    calm = np.zeros(n, bool)
    calm[8:] = np.abs(c[8:] / c[:-8] - 1) <= 0.05
    hit = np.zeros(n, bool)
    ls = pd.Series(l)
    for L in range(1, 9):
        mn = ls.rolling(L, min_periods=L).min().values
        base = np.r_[np.full(L, np.nan), c[:-L]]
        cb = np.r_[np.zeros(L, bool), calm[:-L]]
        hit |= cb & (mn <= base * 0.85) & (np.arange(n) - L >= 8)
    nz = np.flatnonzero(a["qv"] > 0)
    if not len(nz):
        return np.array([], dtype=np.int64)
    hit &= (np.arange(n) >= nz[0] + 96) & (np.arange(n) <= nz[-1])
    hit &= a["qv"] > 0
    out, last = [], -10 ** 9
    for j in np.flatnonzero(hit):
        if j - last >= 96:
            out.append(int(j)); last = j
    return np.array(out, dtype=np.int64)


def main():
    K = load_k()
    U = json.load(open(f"{OUT}/universe.json"))
    PU = pickle.load(open("s15/kr_pumps.pkl", "rb"))
    rows = []
    for p, u in U.items():
        a = K[p]
        for kind, J in (("pump", PU.get(p, np.zeros(0, np.int64))), ("dump", dumps(a))):
            for j in J:
                t = int(a["t"][j]) + BAR                                   # закрытие свечи события
                if t < T0 or t >= T1:
                    continue
                rows.append((p, int(j), t, kind, (u["spot0"] is None) or (t < u["spot0"])))
    E = pd.DataFrame(rows, columns=["p", "j", "t", "kind", "nospot"])
    E.to_pickle(f"{OUT}/events.pkl")
    mo = (T1 - T0) / (30.44 * DAY)
    for kind in ("pump", "dump"):
        x = E[E.kind == kind]
        for ns in (True, False):
            y = x[x.nospot == ns]
            h1 = (y.t < MID).sum()
            print(f"{kind} {'без спота' if ns else 'со спотом'}: {len(y)} ({len(y) / mo:.1f} в месяц), половины {h1} / "
                  f"{len(y) - h1}, монет {y.p.nunique()}")
    y = E[E.nospot]
    q = pd.to_datetime(y.t, unit="s").dt.to_period("Q")
    print("без спота по кварталам:\n", pd.crosstab(q, y.kind).to_string())
    days = {}
    for r in y.itertuples():
        d0 = (r.t // DAY) * DAY
        for k in (-1, 0, 1, 2):
            days.setdefault(r.p, set()).add(pd.Timestamp(d0 + k * DAY, unit="s").strftime("%Y-%m-%d"))
    days = {p: sorted(v) for p, v in days.items()}
    json.dump(days, open(f"{OUT}/met_days.json", "w"))
    print(f"сутки метрик вокруг событий без спота: {sum(len(v) for v in days.values())} у {len(days)} перпов")
    met = set(f[:-4] for f in os.listdir("s228/met"))
    print(f"из них перпов с готовыми метриками s228: {sum(p in met for p in days)}")


if __name__ == "__main__":
    main()
