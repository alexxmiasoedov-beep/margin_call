"""s227 — оценка перебора по CYBER (метод и порог — ВЫВОДЫ.md, записаны до расчёта доходов).

Для каждого исхода и каждой «эпохи» (весь период: A до 2025, B 2025, C 2026; эпоха канала: A' до 10.2025, B' до 04.2026,
C' с 04.2026): лучшее по t на B правило из прошедших отсев (s216/bombe.py) → честные сделки (одна за раз) на C и на свежем
отрезке D (22.10–19.11.2026), плацебо (та же сделка за 45 / 90 / 135 сут до входа), контроль (лучшее по B правило трёх
прогонов на перемешанных доходах — на настоящих доходах C). Условия на D переносятся с точными порогами, посчитанными на A
(та же логика, что s216/bombe.build, включая SPARSE; совпадение масок проверяется).
Запуск из /home/user/mc_data после run_bombe.sh: python3 <repo>/research/s227/evaluate.py"""
import datetime
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s216"))
os.environ.setdefault("SPARSE", "1")
import bombe  # noqa: E402

UTC = datetime.timezone.utc
WEEK, D = 7 * 86400, 86400
ERAS = {"main": ("s227", "2025-01-01", "2026-01-01"), "chan": ("s227c", "2025-10-01", "2026-04-01")}
OUTS = ["y_l1", "y_s1", "y_l4", "y_s4", "y_l24", "y_s24", "y_l72", "y_s72"]
MINN = 150


def ts(d):
    return datetime.datetime.fromisoformat(d).replace(tzinfo=UTC).timestamp()


def conds(Fr, A, FE):
    """Те же условия и в том же порядке, что bombe.build (SPARSE): [(функция маски, имя)] по признакам, пороги — на A."""
    out, masks = [], []
    for f in FE:
        x = Fr[f].to_numpy(np.float64); xa = x[A & np.isfinite(x)]
        if len(xa) < 300 or np.unique(xa).size < 2:
            continue
        u, cnt = np.unique(xa, return_counts=True)
        if cnt.max() >= 0.8 * len(xa):
            mode = u[cnt.argmax()]; ev = xa[xa != mode]; up = mode <= ev.min() if len(ev) else True
            cand = [(lambda X, f=f, mode=mode: (X[f].to_numpy(float) != mode) & np.isfinite(X[f].to_numpy(float)), f"{f} ≠ {mode:.4g}")]
            if len(ev) >= 300:
                for q in sorted(set(np.round(np.quantile(ev, [0.2, 0.4, 0.6, 0.8]), 10))):
                    cand.append((lambda X, f=f, mode=mode, q=q, up=up: (((X[f].to_numpy(float) >= q) if up else (X[f].to_numpy(float) <= q))
                                                                         & (X[f].to_numpy(float) != mode) & np.isfinite(X[f].to_numpy(float))),
                                 f"{f} {'≥' if up else '≤'} {q:.4g}"))
            for fn, nm in cand:
                m = fn(Fr)
                if m[A].sum() >= MINN and m[A].mean() < 0.95 and not any((m == c).all() for c in masks[-8:]):
                    masks.append(m); out.append((fn, nm))
            continue
        for q in sorted(set(np.round(np.quantile(xa, [0.2, 0.4, 0.6, 0.8]), 10))):
            lo = lambda X, f=f, q=q: (X[f].to_numpy(float) <= q) & np.isfinite(X[f].to_numpy(float))
            hi = lambda X, f=f, q=q: (X[f].to_numpy(float) >= q) & np.isfinite(X[f].to_numpy(float))
            for fn, nm in ((lo, f"{f} ≤ {q:.4g}"), (hi, f"{f} ≥ {q:.4g}")):
                m = fn(Fr)
                if 0.05 < m[A].mean() < 0.95 and not any((m == c).all() for c in masks[-8:]):
                    masks.append(m); out.append((fn, nm))
    return out, np.array(masks, bool)


def ct(x, t):
    x = np.asarray(x, float); w = (np.asarray(t, float) // WEEK).astype(np.int64); ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 3:
        return (x.mean() if len(x) else np.nan), np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum(); se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x)


def honest(sel, T, end):
    take, busy = [], -1
    for i in np.flatnonzero(sel & np.isfinite(end)):
        if T[i] >= busy:
            take.append(i); busy = end[i]
    return np.array(take, int)


def best(R):
    P = R[R.passB]
    return None if not len(P) else P.sort_values("z_B", ascending=False).iloc[0]


def main():
    Dfr = pd.read_pickle("s227D_feat.pkl").sort_values("T").reset_index(drop=True)
    lines = []
    for era, (pfx, ta, tb) in ERAS.items():
        F0 = pd.read_pickle(f"{pfx}_feat.pkl").sort_values(["T", "s"]).reset_index(drop=True)
        for col in OUTS:
            Fr = F0[F0[col].notna()].reset_index(drop=True)
            T = Fr["T"].to_numpy(np.int64); seg = np.where(T < ts(ta), 0, np.where(T < ts(tb), 1, 2))
            FE = [c for c in Fr.columns if c not in bombe.OUTC | {"s", "T"} and not c.startswith(("y_", "u_"))
                  and pd.api.types.is_numeric_dtype(Fr[c])]
            cl, M = conds(Fr, seg == 0, FE)
            C0, _, _ = bombe.build(Fr, seg == 0)
            assert C0.shape == M.shape and (C0 == M).all(), "условия не совпали с bombe.build"
            R = pd.read_pickle(f"{pfx}_bombe_{col}.pkl")
            y = Fr[col].to_numpy(float); end = Fr["u_e_" + col[2:]].to_numpy(float); yh = Fr["u_h_" + col[2:]].to_numpy(float)
            months_c = (T[seg == 2].max() - T[seg == 2].min()) / (30.44 * D) if (seg == 2).any() else np.nan
            ypl = {}
            idx = {int(x): i for i, x in enumerate(T)}

            def placebo(tk):
                out = []
                for i in tk:
                    v = [y[idx[T[i] - d * D]] for d in (45, 90, 135) if (T[i] - d * D) in idx and np.isfinite(y[idx[T[i] - d * D]])]
                    out.append(np.mean(v) if v else np.nan)
                return np.array(out)

            def evalrule(row, yy):
                ix = list(row.ix)
                sel = np.logical_and.reduce([M[i] for i in ix])
                tk = honest(sel & (seg == 2), T, end)
                return tk, ix
            b = best(R)
            line = f"\n=== {era} {col}: прошли отсев {int(R.passB.sum())} из {len(R)}"
            if b is None:
                lines.append(line + " — правил нет"); continue
            tk, ix = evalrule(b, y)
            m, t, n = ct(y[tk], T[tk]); mh = np.nanmean(yh[tk]) if len(tk) else np.nan
            pl = placebo(tk); md = np.nanmean(y[tk] - pl) if len(tk) else np.nan
            ctl = []
            for sd in (0, 1, 2):
                Rs = pd.read_pickle(f"{pfx}_bombe_{col}_shuf{sd}.pkl"); bs = best(Rs)
                if bs is None:
                    ctl.append(np.nan); continue
                ts_ = honest(np.logical_and.reduce([M[i] for i in bs.ix]) & (seg == 2), T, end)
                ctl.append(np.mean(y[ts_]) if len(ts_) else np.nan)
            # свежий отрезок D: те же условия с порогами A
            selD = np.logical_and.reduce([cl[i][0](Dfr) for i in ix]) & Dfr[col].notna().to_numpy()
            tD = Dfr["T"].to_numpy(np.int64); yD = Dfr[col].to_numpy(float); eD = Dfr["u_e_" + col[2:]].to_numpy(float)
            tkD = honest(selD, tD, eD); mD = np.mean(yD[tkD]) if len(tkD) else np.nan
            P = R[R.passB].sort_values("z_B", ascending=False)
            ok = [("C > 0 и t ≥ 2", m > 0 and t >= 2), ("лучше плацебо", md > 0), ("лучше контроля", m > np.nanmean(ctl)),
                  ("D > 0", mD > 0)]
            line += (f"; у прошедших на C (по правилам) {P.m_C.mean():+.2%}, в плюсе {(P.m_C > 0).mean():.0%}\n"
                     f"  ЛУЧШЕЕ ПО B: {b['правило']} | A {b.m_A:+.2%} (n {b.n_A:.0f}, t {b.z_A:+.1f}) | B {b.m_B:+.2%} (n {b.n_B:.0f}, "
                     f"t {b.z_B:+.1f})\n"
                     f"  честно на C: {n} сделок ({n / months_c:.1f} в мес.), {m:+.2%} (t {t:+.1f}), с хеджем {mh:+.2%}, сверх плацебо "
                     f"{md:+.2%}; контроль (лучшие по B трёх перемешиваний) {', '.join(f'{x:+.2%}' for x in ctl)}; D: {len(tkD)} сделок, "
                     + (f"{mD:+.2%}" if len(tkD) else "—")
                     + "\n  порог: " + "; ".join(f"{a} — {'да' if v else 'нет'}" for a, v in ok)
                     + ("  → ПРОЙДЕН" if all(v for _, v in ok) else "  → не пройден"))
            top = P.head(10)
            line += "\n  10 лучших по B (A / B / C по наблюдениям): " + " || ".join(
                f"{r['правило']}: {r.m_A:+.2%}/{r.m_B:+.2%}/{r.m_C:+.2%} (n_C {r.n_C:.0f})" for _, r in top.iterrows())
            lines.append(line)
            print(line, flush=True)
    open("s227/evaluate.txt", "w").write("\n".join(lines))


if __name__ == "__main__":
    main()
