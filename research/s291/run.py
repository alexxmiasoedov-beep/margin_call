"""s291 — расчёт по записи ВЫВОДЫ.md (коммит 67bac4e): Г2 (одновременность внимания) и Г3 (расстояние до
365-дневного максимума) на входах ⏰ 🇰🇷 🔝 👀 🛒. Признаки — prep.py (s291_entries.pkl), доходы — уже посчитанные
сделки s270, s277, s285 (fastbt: комиссия, стоп + 0,2%, фандинг; hed — с хеджем индексом альтов; pl — плацебо).
Запуск из /home/user/mc_data: python3 -I <repo>/research/s291/run.py → /home/user/mc_data/s291_report.txt"""
import numpy as np
import pandas as pd

D0 = "/home/user/mc_data"
PERS = ("2020–2022", "2022–2024", "2024–2026")
MO = {"2020–2022": 24.0, "2022–2024": 24.0, "2024–2026": 24.6}
WEEK = 7 * 86400
out = []


def P(*a):
    s = " ".join(str(x) for x in a)
    out.append(s)
    print(s)


def returns():
    rows = []
    for p in PERS:
        a = pd.read_pickle(f"{D0}/s277_{p}.pkl")
        a = a[a.h.isin(["⏰", "🇰🇷", "👀"]) & a.ex.isin(["8 ч", "24 ч"])][["h", "ex", "s", "te", "net", "hed", "pl", "stop"]]
        b = pd.read_pickle(f"{D0}/s285_{p}.pkl")
        b = b[b.ex.isin(["8 ч", "24 ч"])].assign(h="🔝")[["h", "ex", "s", "te", "net", "hed", "pl", "stop"]]
        c = pd.read_pickle(f"{D0}/s270_{p}.pkl")
        c = c[(c.grp == "S") & (c.side == -1) & (c.sl == 0.10) & c.hold.isin([8, 24])]
        c = c.assign(h="🛒", ex=c.hold.map({8: "8 ч", 24: "24 ч"}))[["h", "ex", "s", "te", "net", "hed", "pl", "stop"]]
        x = pd.concat([a, b, c], ignore_index=True)
        x["per"] = p
        rows.append(x)
    R = pd.concat(rows, ignore_index=True)
    R["te"] = R.te.astype(np.int64)
    return R.drop_duplicates(["per", "h", "ex", "s", "te"])


def ct(x, t):
    x = np.asarray(x, float)
    w = np.asarray(t, np.int64) // WEEK
    ok = np.isfinite(x)
    x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x), np.nan
    m = x.mean()
    s = pd.Series(x - m).groupby(w).sum()
    se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x), se


def dedup(x):
    x = x.sort_values("te")
    keep, last = [], {}
    for i, s, te in zip(x.index, x.s.values, x.te.values):
        if te - last.get(s, -10 ** 12) >= 8 * 3600:
            keep.append(i)
            last[s] = te
    return x.loc[keep]


def delta_line(A, B, col):
    cells, allA, allB, signs = [], [], [], []
    for p in PERS:
        a, b = A[A.per == p], B[B.per == p]
        m1, _, n1, s1 = ct(a[col], a.te)
        m2, _, n2, s2 = ct(b[col], b.te)
        if n1 < 5 or n2 < 5:
            cells.append(f"{p} —")
            signs.append(False)
            continue
        d = m1 - m2
        cells.append(f"{p} Δ {d:+.2%} (t {d / np.hypot(s1, s2):+.1f}; {m1:+.2%} n={n1} / {m2:+.2%} n={n2})")
        signs.append(d > 0)
    m1, _, _, s1 = ct(A[col], A.te)
    m2, _, _, s2 = ct(B[col], B.te)
    d = m1 - m2
    tt = d / np.hypot(s1, s2)
    return cells, d, tt, all(signs)


def twin(x, name):
    """Правило владельца на 2024–2026 гг. и три периода (доход без хеджа)."""
    cells, signs = [], []
    for p in PERS:
        g = x[x.per == p]
        m, t, n, _ = ct(g.net, g.te)
        cells.append(f"{p}: {m:+.2%} (t {t:+.1f}, {n / MO[p]:.1f} в мес.)" if n >= 5 else f"{p}: n={n}")
        signs.append(n >= 5 and m > 0)
    g = x[x.per == "2024–2026"]
    m, t, n, _ = ct(g.net, g.te)
    mid = float(np.median(g.te)) if len(g) else 0
    h1, h2 = g[g.te < mid].net.mean(), g[g.te >= mid].net.mean()
    md, _, _, _ = ct(g.net - g.pl, g.te)
    mh, th, _, _ = ct(g.hed, g.te)
    A = x[x.per.isin(PERS)]
    ma, ta, na, _ = ct(A.net, A.te)
    ok26 = n / MO["2024–2026"] >= 20 and t >= 3 and h1 > 0 and h2 > 0 and md > 0
    P(f"  {name}: " + "; ".join(cells))
    P(f"    2024–2026: половины {h1:+.2%} / {h2:+.2%}, сверх плацебо {md:+.2%}, с хеджем {mh:+.2%} (t {th:+.1f}); "
      f"вместе {ma:+.2%} (t {ta:+.1f}) → правило владельца {'да' if ok26 else 'нет'}, три периода "
      f"{'да' if all(signs) and ta >= 3 else 'нет'}")


def main():
    F = pd.read_pickle(f"{D0}/s291_entries.pkl")
    R = returns().merge(F[["per", "h", "ex", "s", "te", "C", "d365", "age365"]], on=["per", "h", "ex", "s", "te"],
                        how="inner")
    R["cg"] = np.select([R.C == 0, R.C <= 2], ["0", "1–2"], "≥3")
    R.loc[R.C.isna(), "cg"] = "?"
    R["dg"] = np.select([~R.age365, R.d365 <= -0.5, R.d365 < 0], ["молодые", "далеко", "близко"], "новый максимум")
    R.loc[R.d365.isna(), "dg"] = "?"
    for ex in ("8 ч", "24 ч"):
        X = R[R.ex == ex]
        U = dedup(X)
        P(f"\n######## выход {ex}, стоп 10%{' — основной' if ex == '8 ч' else ' (для отчёта)'}")
        P(f"общий набор после повторов: " + ", ".join(f"{p} {int((U.per == p).sum())}" for p in PERS))
        P("\n## Г2 — одновременность: Δ = C = 0 − C ≥ 3")
        for col, lab in (("hed", "с хеджем (основной)"), ("net", "без хеджа")):
            cells, d, tt, allpos = delta_line(U[U.cg == "0"], U[U.cg == "≥3"], col)
            P(f"  общий набор, {lab}: " + "; ".join(cells))
            P(f"    вместе Δ {d:+.2%} (t {tt:+.1f}); Δ > 0 во всех — {'да' if allpos else 'нет'} → " +
              ("ПОРОГ МЕХАНИЗМА ПРОЙДЕН" if allpos and tt >= 2 and col == "hed" else "не пройден" if col == "hed" else ""))
        for h in ("⏰", "🇰🇷", "🔝", "🛒", "👀"):
            x = X[X.h == h]
            cells, d, tt, allpos = delta_line(x[x.cg == "0"], x[x.cg == "≥3"], "hed")
            P(f"  {h}, с хеджем: " + "; ".join(cells) + f"; вместе Δ {d:+.2%} (t {tt:+.1f})")
        P("  средние по группам (общий набор, с хеджем): " + "; ".join(
            f"{p}: " + ", ".join(f"C {g} {ct(U[(U.per == p) & (U.cg == g)].hed, U[(U.per == p) & (U.cg == g)].te)[0]:+.2%}"
                                 for g in ("0", "1–2", "≥3")) for p in PERS))
        P("\n## Г3 — расстояние до 365-дневного максимума: Δ = далеко (≤ −50%) − остальные старые (> −50%)")
        old = U[U.dg.isin(["далеко", "близко", "новый максимум"])]
        for col, lab in (("hed", "с хеджем (основной)"), ("net", "без хеджа")):
            cells, d, tt, allpos = delta_line(old[old.dg == "далеко"], old[old.dg != "далеко"], col)
            P(f"  общий набор, {lab}: " + "; ".join(cells))
            P(f"    вместе Δ {d:+.2%} (t {tt:+.1f}); Δ > 0 во всех — {'да' if allpos else 'нет'} → " +
              ("ПОРОГ МЕХАНИЗМА ПРОЙДЕН" if allpos and tt >= 2 and col == "hed" else "не пройден" if col == "hed" else ""))
        cells, d, tt, allpos = delta_line(old[old.dg == "новый максимум"], old[old.dg != "новый максимум"], "hed")
        P("  новый максимум − остальные старые (с хеджем): " + "; ".join(cells) + f"; вместе Δ {d:+.2%} (t {tt:+.1f})")
        cells, d, tt, allpos = delta_line(U[U.dg == "молодые"], old, "hed")
        P("  молодые − старые (с хеджем): " + "; ".join(cells) + f"; вместе Δ {d:+.2%} (t {tt:+.1f})")
        for h in ("⏰", "🇰🇷", "🔝", "🛒", "👀"):
            x = X[(X.h == h) & X.dg.isin(["далеко", "близко", "новый максимум"])]
            cells, d, tt, allpos = delta_line(x[x.dg == "далеко"], x[x.dg != "далеко"], "hed")
            P(f"  {h}, с хеджем: " + "; ".join(cells) + f"; вместе Δ {d:+.2%} (t {tt:+.1f})")
        P("\n## Двойники (доход без хеджа)")
        twin(U[U.cg == "0"], "общий набор, C = 0")
        twin(U[U.dg == "далеко"], "общий набор, далеко")
        twin(U, "общий набор целиком (для сравнения)")
        for h in ("⏰", "🇰🇷", "🔝", "🛒"):
            twin(X[(X.h == h) & (X.cg == "0")], f"{h}, C = 0")
            twin(X[(X.h == h) & (X.dg == "далеко")], f"{h}, далеко")
    open(f"{D0}/s291_report.txt", "w").write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
