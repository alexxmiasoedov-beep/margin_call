"""s223 — комитет правил (метод — ВЫВОДЫ.md, записан до расчёта): 100 лучших по t на B правил из прошедших отсев, голос
наблюдения — сколько из них выполнено; порог голосов k из {1, 3, 10, 30} — по наибольшему t честных сделок на B; итог на C.
Честные сделки: вход на закрытии T, одна сделка на монету до выхода (u_e_<исход>), доход с хеджем индексом альтов, t по
неделям. Контроль — тот же комитет из перебора на перемешанных исходах (правила и k выбраны по перемешанным исходам),
доход — настоящий. Плацебо — та же сделка той же монеты за 45/90/135 сут до входа, тоже с хеджем.
Запуск из /home/user/mc_data после bombe.py (PFX=s223): python3 <repo>/research/s223/committee.py [исход …]"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s216", "s187"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
PFX = os.environ.setdefault("PFX", "s223")          # s224a: часовая сетка (PFX=s224h)
import bombe  # noqa: E402

DAY, WEEK = 86400, 7 * 86400
KS, TOPK = (1, 3, 10, 30), 100
MIDC = pd.Timestamp("2026-07-11", tz="UTC").timestamp()
C1 = pd.Timestamp("2026-10-21", tz="UTC").timestamp()
PAR = {"y_hs4": (-1, 0.10, 4), "y_hs24": (-1, 0.25, 24), "y_hs48": (-1, 0.25, 48), "y_hs168": (-1, 0.50, 168),
       "y_hl4": (1, 0.10, 4), "y_hl24": (1, 0.25, 24), "y_hl48": (1, 0.25, 48), "y_hl168": (1, 0.50, 168)}


def ct(x, t):
    x = np.asarray(x, float); w = (np.asarray(t, float) // WEEK).astype(np.int64); ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return (x.mean() if len(x) else np.nan), np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum(); se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x)


def honest(sel, D, y, end):
    """Честные сделки по отмеченным наблюдениям: одна сделка на монету до выхода. → индексы наблюдений."""
    idx = np.flatnonzero(sel & np.isfinite(y) & np.isfinite(end))
    busy, take = {}, []
    for i in idx:                                             # D отсортирован по T
        s = D.s.iat[i]; T = D["T"].iat[i]
        if T >= busy.get(s, -1):
            take.append(i); busy[s] = end[i]
    return np.array(take, int)


def votes(R, C):
    P = R[R.passB].sort_values("z_B", ascending=False).head(TOPK)
    v = np.zeros(C.shape[1], np.int32)
    for ix in P.ix:
        v += np.logical_and.reduce(C[list(ix)], axis=0)
    return v, len(P)


def pick_k(v, seg, D, y, end):
    best = None
    for k in KS:
        tk = honest((v >= k) & (seg == 1), D, y, end)
        m, t, n = ct(y[tk], D["T"].to_numpy()[tk])
        if n >= 30 and np.isfinite(t) and (best is None or t > best[1]):
            best = (k, t, m, n)
    return best


def placebo(D, tk, col):
    import fastbt as FB  # noqa: E402
    side, sl, hold = PAR[col]
    out = np.full(len(tk), np.nan)
    for j, i in enumerate(tk):
        s = D.s.iat[i]
        if s not in FB.K:
            continue
        t = FB.K[s]["t"].astype(np.int64); v = []
        for d in (45, 90, 135):
            st = D["T"].iat[i] - d * DAY - 900; I = int(np.searchsorted(t, st))
            if 96 <= I < len(t) and t[I] == st:
                okt, net, _, _, tend = FB.trades(s, np.array([I]), sl, hold, side)
                if okt[0]:
                    v.append(net[0] - side * FB.alt_mv(np.array([t[I] + 900]), np.array([tend[0]]))[0])
        out[j] = np.nanmean(v) if v else np.nan
    return out


def shuffled_y(D, y, seed):
    rng = np.random.default_rng(seed); z = y.copy()
    mon = pd.to_datetime(D["T"], unit="s").dt.to_period("M").astype(str).to_numpy()
    for m in np.unique(mon):
        ix = np.flatnonzero(mon == m); z[ix] = z[rng.permutation(ix)]
    return z


def main(cols):
    F = pd.read_pickle(f"{PFX}_feat.pkl").sort_values(["T", "s"]).reset_index(drop=True)
    months = (C1 - bombe.TB) / (30.44 * DAY)
    for col in cols:
        D = F[F[col].notna()].reset_index(drop=True)
        T = D["T"].to_numpy(np.int64); seg = np.where(T < bombe.TA, 0, np.where(T < bombe.TB, 1, 2))
        y = D[col].to_numpy(float); end = D["u_e_" + col[2:]].to_numpy(float)
        C, names, _ = bombe.build(D, seg == 0)
        R = pd.read_pickle(f"{PFX}_bombe_{col}.pkl")
        v, nP = votes(R, C)
        b = pick_k(v, seg, D, y, end)
        print(f"\n=== {col}: правил в комитете {nP} ===")
        if not b:
            print("  на B нет порога k с ≥ 30 сделками"); continue
        k = b[0]
        print(f"  k = {k} (на B: {b[3]} сделок, {b[2]:+.2%}, t {b[1]:+.1f}); на B при других k: " + "; ".join(
            f"k {kk}: " + "{:+.2%} (t {:+.1f}, n {})".format(*ct(y[tt], T[tt])) for kk in KS
            for tt in [honest((v >= kk) & (seg == 1), D, y, end)]))
        tk = honest((v >= k) & (seg == 2), D, y, end)
        m, t, n = ct(y[tk], T[tk])
        h1, h2 = y[tk][T[tk] < MIDC].mean(), y[tk][T[tk] >= MIDC].mean()
        pl = placebo(D, tk, col); md, td, _ = ct(y[tk] - pl, T[tk])
        allc = ct(y[honest(seg == 2, D, y, end)], T[honest(seg == 2, D, y, end)])
        print(f"  C: {n} сделок ({n / months:.1f} в мес.), {m:+.2%} (t {t:+.1f}); половины {h1:+.2%} / {h2:+.2%}; "
              f"сверх плацебо {md:+.2%} (t {td:+.1f}); все наблюдения C честно {allc[0]:+.2%} (n {allc[2]})")
        ctl = []
        for sd in (0, 1, 2):
            Rs = pd.read_pickle(f"{PFX}_bombe_{col}_shuf{sd}.pkl")
            vs, _ = votes(Rs, C)
            ys = shuffled_y(D, y, sd)
            bs = pick_k(vs, seg, D, ys, end)
            if not bs:
                ctl.append(np.nan); continue
            ts = honest((vs >= bs[0]) & (seg == 2), D, y, end)
            ctl.append(ct(y[ts], T[ts])[0])
            print(f"  контроль {sd}: k {bs[0]}, C {ctl[-1]:+.2%} (n {len(ts)})")
        ok = [("t ≥ 3", m > 0 and t >= 3), ("≥ 20 в мес.", n / months >= 20), ("половины > 0", h1 > 0 and h2 > 0),
              ("сверх плацебо > 0", md > 0), ("лучше контроля", m > np.nanmean(ctl))]
        print("  порог: " + "; ".join(f"{a} — {'да' if c else 'нет'}" for a, c in ok)
              + ("  → ПРОЙДЕН" if all(c for _, c in ok) else ""))
        pd.DataFrame({"s": D.s.values[tk], "T": T[tk], "y": y[tk], "pl": pl, "v": v[tk]}).to_pickle(f"{PFX}_comm_{col}.pkl")


if __name__ == "__main__":
    main(sys.argv[1:] or [c for c in PAR if c in pd.read_pickle(f"{PFX}_feat.pkl").columns])
