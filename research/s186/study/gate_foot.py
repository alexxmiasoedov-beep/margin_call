"""s186 — след ребаланса токенов Gate на самой площадке хеджа: оборот 15-мин свечей перпа Gate USDT-M в 16:00–16:15 UTC
(время ребаланса) против других якорей, по |ходу за 24 ч до якоря| и по оценке потока (M из gate_flow: оборот токенов).

Свечи — Gate /futures/usdt/candlesticks 15m, последние 10000 точек (~104 сут, 08–11.2026; глубже API не отдаёт).
Только оборот (без цены после якоря и знака сделок). Лог — gate_foot.log, кэш — gate_fut15.pkl. Доходы не считаются."""
import os
import pickle
import time

import numpy as np
import pandas as pd

import common186 as C

L = C.Log("gate_foot")
GATE = "https://api.gateio.ws/api/v4"
HOURS = (0, 4, 8, 12, 16, 20)
BUCK = [(0, 0.02), (0.02, 0.05), (0.05, 0.10), (0.10, 9.0)]


def fetch(u):
    rows = []
    t1 = int(time.time()) // 900 * 900
    for _ in range(5):
        d = C.jget(f"{GATE}/futures/usdt/candlesticks?contract={u}_USDT&interval=15m&from={t1 - 1999 * 900}&to={t1}")
        time.sleep(0.12)
        if not isinstance(d, list) or not d:
            break
        rows += [(int(x["t"]), float(x.get("sum") or 0), float(x["c"])) for x in d]
        t1 = int(d[0]["t"]) - 900
    if not rows:
        return None
    a = np.array(sorted(set(rows)))
    return pd.DataFrame({"qv": a[:, 1], "c": a[:, 2]}, index=a[:, 0].astype(np.int64))


def main():
    U = pickle.load(open(f"{C.OUT}/lt_universe.pkl", "rb"))
    G = U["G"]
    perp = set(U["U"][U["U"].perp].und)
    unds = sorted(set(G.und) & perp)
    path = f"{C.OUT}/gate_fut15.pkl"
    F = pickle.load(open(path, "rb")) if os.path.exists(path) else {}
    for u in unds:
        if u not in F:
            F[u] = fetch(u)
            if len(F) % 20 == 0:
                pickle.dump(F, open(path, "wb"))
    pickle.dump(F, open(path, "wb"))
    # оценка M (K = 1) на последние 104 сут: Σ L(L−1)·оборот токенов за 7 сут до суток
    gd = pickle.load(open(f"{C.OUT}/gate_daily.pkl", "rb"))
    lev = dict(zip(G.pair, G.lev))
    und = dict(zip(G.pair, G.und))
    Mu = {}
    for pair, df in gd.items():
        if pair in lev:
            L0 = float(lev[pair])
            m = L0 * (L0 - 1) * df.qv.rolling(7, min_periods=1).mean().shift(1)
            Mu.setdefault(und[pair], []).append(m)
    Mu = {u: pd.concat(v, axis=1).sum(axis=1) for u, v in Mu.items()}
    rows = []
    for u, df in F.items():
        if df is None or len(df) < 96 * 20:
            continue
        g0 = int(df.index.min())
        n = (int(df.index.max()) - g0) // 900 + 1
        qg = np.full(n, np.nan)
        cg = np.full(n, np.nan)
        ix = (df.index.values - g0) // 900
        qg[ix] = df.qv.values
        cg[ix] = df.c.values
        d0 = (g0 // C.DAY + 15) * C.DAY
        days = np.arange(d0, g0 + (n - 96) * 900, C.DAY)
        for h in HOURS:
            s = (days + h * 3600 - g0) // 900
            ok = (s + 1 < n)
            s = s[ok]
            dd = days[ok]
            with np.errstate(all="ignore"):
                r24 = cg[s - 1] / cg[s - 97] - 1
                base = np.nanmedian(np.vstack([qg[s - 96 * k] for k in range(1, 15)]), axis=0)
            daily = pd.Series(qg).rolling(672, min_periods=300).sum().values / 7
            M = Mu.get(u)
            mval = M.reindex(dd).values if M is not None else np.full(len(dd), np.nan)
            rows.append(pd.DataFrame({"u": u, "D": dd, "H": h, "r24": r24, "ratio": qg[s] / base,
                                      "phi": mval * np.abs(r24) / daily[s - 1]}))
    X = pd.concat(rows, ignore_index=True)
    X = X[np.isfinite(X.r24) & np.isfinite(X.ratio)]
    X["ar"] = X.r24.abs()
    L(f"монет {X.u.nunique()}, суток {X.D.nunique()} ({C.iso(X.D.min())} … {C.iso(X.D.max())})")
    L("медиана (оборот свечи [T, T+15 мин) перпа Gate / её медиана за 14 сут) по |r24| <2 / 2–5 / 5–10 / ≥10%:")
    for h in HOURS:
        x = X[X.H == h]
        med = [x.ratio[(x.ar >= a) & (x.ar < b)].median() for a, b in BUCK]
        nn = [int(((x.ar >= a) & (x.ar < b)).sum()) for a, b in BUCK]
        L(f"  {h:02d} UTC: " + " / ".join(f"{m:.2f}" for m in med) + f"   (n {nn})")
    L("16 UTC против остальных якорей при |r24| ≥ 5%, по оценке потока к суточному обороту перпа Gate (K = 1):")
    for lo, hi in ((0, 0.01), (0.01, 0.05), (0.05, 9)):
        a = X[(X.H == 16) & (X.ar >= 0.05) & (X.phi >= lo) & (X.phi < hi)]
        b = X[(X.H != 16) & (X.ar >= 0.05) & (X.phi >= lo) & (X.phi < hi)]
        L(f"  поток {lo * 100:.0f}–{hi * 100:.0f}%: 16 UTC медиана {a.ratio.median():.2f} (n {len(a)}), другие якоря "
          f"{b.ratio.median():.2f} (n {len(b)})")


if __name__ == "__main__":
    main()
