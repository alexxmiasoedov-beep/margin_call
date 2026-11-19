"""s179 — пересечение вонных круглых событий (2024–2026) с входами действующих корейских и спотовых журналов.
Только время и монета; доходы журналов не читаются (берутся столбцы s и t).

Запуск: python3 -I probe_round_overlap.py <папка данных>
Журналы: 🔝 — s65/trades.pkl; 👀 — s83/trades.pkl; ⏰ — s88/trades.pkl (open9, рост часа ≥ 5%, доля Кореи ≥ 20%);
🛒 — s49/trades.pkl (доля спота ≥ 26%). Пересечение — вход журнала по тому же перпу в ±24 ч от события; обратная сторона — доля входов журналов
с вонным круглым пробоем {1…9} той же монеты за 24 ч до входа.
"""
import importlib.util
import os
import pickle
import sys

import numpy as np
import pandas as pd

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("prl", os.path.join(HERE, "probe_round_levels.py"))
prl = importlib.util.module_from_spec(spec)
sys.argv = [sys.argv[0], D]
spec.loader.exec_module(prl)


def journals():
    J = {}
    a = pd.read_pickle(os.path.join(D, "s65/trades.pkl"))[["s", "t"]]; J["🔝"] = a
    a = pd.read_pickle(os.path.join(D, "s83/trades.pkl"))[["s", "t"]]; J["👀"] = a
    a = pd.read_pickle(os.path.join(D, "s88/trades.pkl"))
    a = a[(a.open9.astype(bool)) & (a.r1 >= 0.05) & (a.share >= 0.20)][["s", "t"]]; J["⏰"] = a
    a = pd.read_pickle(os.path.join(D, "s49/trades.pkl"))
    a = a[a.share >= 0.26][["s", "t"]]; J["🛒"] = a
    for k, v in J.items():
        v = v.copy()
        v["s"] = v.s.astype(str).str.replace("USDT$", "", regex=True)
        v["t"] = pd.to_numeric(v.t) if np.issubdtype(v.t.dtype, np.number) else pd.to_datetime(v.t, utc=True).astype("int64") // 10 ** 9
        J[k] = v
    return J


def main():
    t0, t1 = pd.Timestamp("2024-10-01", tz="UTC").timestamp(), pd.Timestamp("2026-10-19", tz="UTC").timestamp()
    K = pickle.load(open(os.path.join(D, "s2/fund2y.pkl"), "rb"))
    base = {}
    for s in K:
        for p in ("1000000", "1000", "1M", ""):
            if s.startswith(p) and len(s) > len(p):
                base.setdefault(s[len(p):], s)
    kr, _ = prl.kr_series("2024–2026")
    ev = []
    for (ex, coin), (t, c, v) in kr.items():
        fut = base.get(coin)
        if fut is None:
            continue
        for sig, tl in prl.kr_events(t, c, v, t0, t1).items():
            if "круглые" in sig:
                ev += [(sig, ex, coin, fut, int(x)) for x in tl]
    E = pd.DataFrame(ev, columns=["sig", "ex", "coin", "fut", "t"])
    E["day"] = E.t // 86400
    E = E.sort_values("t").drop_duplicates(["sig", "coin", "day"])
    J = journals()
    for k, v in J.items():
        tt = v.t.values
        print(f"журнал {k}: входов {len(v)}, первый {pd.Timestamp(tt.min(), unit='s').date()}, последний {pd.Timestamp(tt.max(), unit='s').date()}")
    for sig, g in E.groupby("sig"):
        line = f"{sig}: событий {len(g)}"
        anyj = np.zeros(len(g), bool)
        for k, v in J.items():
            hit = []
            for _, r in g.iterrows():
                tt = v.t.values[v.s.values == r.fut]
                hit.append(bool(len(tt)) and bool(np.any(np.abs(tt - r.t) <= 86400)))
            hit = np.array(hit)
            anyj |= hit
            line += f"; с {k} в ±24 ч — {hit.mean():.0%}"
        line += f"; хоть с одним — {anyj.mean():.0%}; без журналов в месяц {(~anyj).sum() / ((t1 - t0) / 86400 / 30.44):.1f}"
        print(line)


def journal_side():
    """Обратная сторона: доля входов журналов, у которых за 24 ч до входа был вонный круглый пробой той же монеты."""
    t0, t1 = pd.Timestamp("2024-10-01", tz="UTC").timestamp(), pd.Timestamp("2026-10-19", tz="UTC").timestamp()
    K = pickle.load(open(os.path.join(D, "s2/fund2y.pkl"), "rb"))
    base = {}
    for s in K:
        for p in ("1000000", "1000", "1M", ""):
            if s.startswith(p) and len(s) > len(p):
                base.setdefault(s[len(p):], s)
    kr, _ = prl.kr_series("2024–2026")
    ev = []
    for (ex, coin), (t, c, v) in kr.items():
        fut = base.get(coin)
        if fut is None:
            continue
        for sig, tl in prl.kr_events(t, c, v, t0, t1).items():
            if sig.startswith("₩ A {1…9} круглые"):
                ev += [(fut, int(x)) for x in tl]
    E = pd.DataFrame(ev, columns=["fut", "t"])
    J = journals()
    for k, v in J.items():
        v = v[(v.t >= t0) & (v.t < t1)]
        hit = []
        for _, r in v.iterrows():
            tt = E.t.values[E.fut.values == r.s]
            hit.append(bool(len(tt)) and bool(np.any((tt <= r.t) & (tt > r.t - 86400))))
        print(f"журнал {k}: входов {len(v)}, с вонным круглым пробоем {{1…9}} за 24 ч до входа — {np.mean(hit):.0%}")


if __name__ == "__main__":
    main()
    journal_side()
