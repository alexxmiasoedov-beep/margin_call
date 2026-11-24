"""s275 — условные описательные статистики на отрезке замысла 01.10.2022–01.10.2023 (часовые шаги, вселенная — топ-100).
Это часть замысла гипотез Г2 и Г4: как ведёт себя остаток после крупного хода монеты в зависимости от того,
двигались ли её «близнецы», и догоняют ли отставшие широкую волну своей группы. Только наклоны и средние ходы
остатков (без комиссий, стопов и правил выхода); на других отрезках эти величины не считаются — там только частоты.

- остаток e1 = r − a − b·BTC − c·альты (коэффициенты с прошлого месяца);
- близнецы монеты — 3 монеты вселенной с наибольшей корреляцией остатков e1 за прошлый месяц;
- рывок: сумма остатка за 2 ч ≥ 3σ₂ (σ₂ — СО 2-часовых сумм остатка в прошлом месяце), не чаще раза в 8 ч;
  «изолированный» — корзина близнецов за те же 2 ч ≤ +1σ своей 2-часовой суммы, иначе «вместе с близнецами»;
  y — спред «монета − близнецы» за следующие 8 ч;
- волна группы (сектор, подсектор или сеть, ≥ 4 членов): корзина за час ≥ 2σ, ≥ 60% членов с остатком ≥ +0,5σ;
  «отставшие» — члены с остатком часа ≤ 0; y — «отставший − корзина» за следующие 4 ч.
Запуск: из /home/user/mc_data — python3 -I <repo>/research/s275/study/cond_design.py → OUT/cond_design.txt"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common275 import DESIGN, H, OUT, load_k, panel, perps, sectors, ts, universe  # noqa: E402
from leadlag_design import alt_factor, month_starts  # noqa: E402

PER = "2022–2024"
LINES = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LINES.append(s)


def rsum(x, k):
    """Скользящая сумма за k шагов, кончающаяся на шаге i (nan при пропуске)."""
    c = np.concatenate([[0.0], np.cumsum(np.where(np.isfinite(x), x, 0.0))])
    bad = np.concatenate([[0], np.cumsum(~np.isfinite(x))])
    out = np.full(len(x), np.nan)
    out[k - 1:] = c[k:] - c[:-k]
    nb = np.zeros(len(x), int); nb[k - 1:] = bad[k:] - bad[:-k]
    out[nb > 0] = np.nan
    return out


def fsum(x, i, h):
    v = x[i + 1:i + 1 + h]
    return v.sum() if len(v) == h and np.isfinite(v).all() else np.nan


def main():
    K = load_k(PER)
    P = perps(K)
    SEC = sectors()
    LR = universe(K, P, PER)
    pidx = {p: k for k, p in enumerate(P)}
    iB = pidx["BTC"]
    t0, t1 = DESIGN
    T, LC, QV = panel(K, P, t0, t1, H)
    R = np.full(LC.shape, np.nan); R[:, 1:] = LC[:, 1:] - LC[:, :-1]
    alt = alt_factor(R, QV, iB, 24)
    btc = R[iB]
    X = np.column_stack([np.ones(R.shape[1]), btc, alt])
    MS = month_starts()
    jumps = []; waves = []
    for mi in range(len(MS) - 1):
        a0, a1 = MS[mi], MS[mi + 1]
        f0 = MS[mi - 1] if mi > 0 else ts("2022-10-01")
        ev = (T > a0) & (T <= a1); fit = (T > f0) & (T <= a0)
        U = [p for p in sorted(LR.get(int(a0 // 86400 * 86400), ())) if p in pidx and p != "BTC"]
        U = [p for p in U if np.isfinite(R[pidx[p], ev]).mean() >= 0.9 and np.isfinite(R[pidx[p], fit]).mean() >= 0.9]
        E = {}
        for p in U:
            y = R[pidx[p]]
            ok = fit & np.isfinite(y) & np.isfinite(X).all(1)
            b, *_ = np.linalg.lstsq(X[ok], y[ok], rcond=None)
            E[p] = y - X @ b                                   # весь ряд; оценка — по ev
        names = sorted(E)
        Mf = np.array([E[p][fit] for p in names]); okc = np.isfinite(Mf).all(0)
        C = np.corrcoef(Mf[:, okc]); np.fill_diagonal(C, -9)
        twins = {p: [names[j] for j in np.argsort(-C[i])[:3]] for i, p in enumerate(names)}
        evi = np.flatnonzero(ev)
        # рывки и близнецы
        for p in names:
            e = E[p]
            s2 = rsum(e, 2)
            sig = np.nanstd(s2[fit][::2])
            tb = np.nanmean(np.array([E[q] for q in twins[p]]), axis=0)
            tb2 = rsum(tb, 2); sig_t = np.nanstd(tb2[fit][::2])
            last = -10 ** 9
            for i in evi:
                if not np.isfinite(s2[i]) or abs(s2[i]) < 3 * sig or i - last < 8:
                    continue
                last = i
                y = fsum(e - tb, i, 8)
                iso = (tb2[i] * np.sign(s2[i])) <= sig_t
                jumps.append((p, i, s2[i] / sig, s2[i], y, iso, s2[i] > 0, T[i]))
        # волны групп
        groups = {}
        for p in names:
            d = SEC.get(p, {})
            for kind in ("sector", "subsector"):
                if d.get(kind):
                    groups.setdefault((kind, d[kind]), []).append(p)
            if d.get("eco") and d["eco"] != "Ethereum":
                groups.setdefault(("eco", d["eco"]), []).append(p)
        for g, mem in groups.items():
            if len(mem) < 4:
                continue
            M = np.array([E[p] for p in mem])
            with np.errstate(all="ignore"):
                bk = np.nanmean(M, axis=0)
            sig_b = np.nanstd(bk[fit]); sig_i = np.nanstd(M[:, fit], axis=1)
            for i in evi:
                if not np.isfinite(bk[i]) or abs(bk[i]) < 2 * sig_b:
                    continue
                sgn = np.sign(bk[i])
                breadth = np.nanmean((M[:, i] * sgn) >= 0.5 * sig_i)
                if breadth < 0.6:
                    continue
                for j, p in enumerate(mem):
                    if M[j, i] * sgn <= 0:
                        others = np.delete(M, j, axis=0)
                        with np.errstate(all="ignore"):
                            ob = np.nanmean(others, axis=0)
                        waves.append((g, p, i, sgn, fsum(M[j] - ob, i, 4), T[i]))
    say("s275 — условные статистики остатков на отрезке замысла 01.10.2022–01.10.2023 (топ-100)")
    J = np.array([(z, x, y, iso, up) for _, _, z, x, y, iso, up, _ in jumps], dtype=float)
    months = (t1 - t0) / (30.44 * 86400) * 11 / 12
    say(f"\n## Рывки остатка за 2 ч ≥ 3σ: всего {len(J)} ({len(J) / months:.0f} в месяц на топ-100)")
    for up in (1, 0):
        for iso in (1, 0):
            m = (J[:, 4] == up) & (J[:, 3] == iso) & np.isfinite(J[:, 2])
            if m.sum() < 10:
                continue
            x, y = J[m, 1], J[m, 2]
            b = np.sum(x * y) / np.sum(x * x)
            say(f"  {'вверх' if up else 'вниз '}, {'изолированный' if iso else 'вместе с близнецами'}: n {m.sum()} "
                f"({m.sum() / months:.0f} в мес.), ход рывка медиана {np.median(x):+.2%}, спред «монета − близнецы» "
                f"за 8 ч: среднее {np.mean(y):+.2%}, медиана {np.median(y):+.2%}, СО {np.std(y):.2%}, наклон b {b:+.3f}")
    W = waves
    say(f"\n## Волны групп (корзина ≥ 2σ за час, широта ≥ 60%): отставших-событий {len(W)} ({len(W) / months:.0f} в мес.)")
    for kind in ("sector", "subsector", "eco"):
        ys = np.array([w[4] * w[3] for w in W if w[0][0] == kind and np.isfinite(w[4])])
        if len(ys) < 10:
            continue
        nh = len({(w[0], w[2]) for w in W if w[0][0] == kind})
        say(f"  {kind}: волн {nh}, отставших {len(ys)}; «отставший − корзина» за 4 ч в сторону волны: среднее "
            f"{np.mean(ys):+.2%}, медиана {np.median(ys):+.2%}, СО {np.std(ys):.2%}")
    open(f"{OUT}/cond_design.txt", "w").write("\n".join(LINES) + "\n")


if __name__ == "__main__":
    main()
