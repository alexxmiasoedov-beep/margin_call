"""s232 — послужной список вкладчика для 🐋 (метод — ВЫВОДЫ.md, записан до расчёта).
Сделки 🐋 трёх периодов (s182_g2_<период>.pkl), клиент — адрес пополнения (s182_origin.pkl, frm). Список — средний доход
с хеджем прошлых сделок того же адреса, закрытых до входа. Группы: N — списка нет, P — список > 0, M — список ≤ 0.
Запуск из /home/user/mc_data: python3 <repo>/research/s232/run.py"""
import numpy as np
import pandas as pd

DAY, WEEK = 86400, 7 * 86400
PERS = ("2020–2022", "2022–2024", "2024–2026")
MON = {"2020–2022": 24.0, "2022–2024": 24.0, "2024–2026": 24.6}


def ct(x, t):
    x = np.asarray(x, float); w = (np.asarray(t, float) // WEEK).astype(np.int64); ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return (x.mean() if len(x) else np.nan), np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum(); se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x)


def diff(y, g, t):
    """Разность средних (g − не g) и t по неделям: МНК y ~ 1 + g с кластерами по неделям."""
    y = np.asarray(y, float); g = np.asarray(g, float); t = np.asarray(t, float)
    ok = np.isfinite(y); y, g, t = y[ok], g[ok], t[ok]
    if g.sum() < 5 or (1 - g).sum() < 5:
        return np.nan, np.nan
    X = np.c_[np.ones_like(g), g]; b = np.linalg.lstsq(X, y, rcond=None)[0]; e = y - X @ b
    w = (t // WEEK).astype(np.int64); XtX = np.linalg.inv(X.T @ X)
    S = sum(np.outer(v, v) for v in (pd.DataFrame(X * e[:, None]).groupby(w).sum().to_numpy()))
    se = np.sqrt(np.diag(XtX @ S @ XtX))
    return b[1], b[1] / se[1]


def main():
    O = pd.read_pickle("s182_origin.pkl")[["tx", "li", "frm"]]
    G = pd.concat([pd.read_pickle(f"s182_g2_{p}.pkl").assign(per=p) for p in PERS])
    G = G.merge(O, on=["tx", "li"], how="left").sort_values("t").reset_index(drop=True)
    assert G.frm.notna().all()
    tr, nprev = np.full(len(G), np.nan), np.zeros(len(G), int)
    hist = {}                                                  # адрес → [(время входа, доход с хеджем)]
    for i, (a, t, h) in enumerate(zip(G.frm, G.t, G.hed)):
        past = [v for tt, v in hist.get(a, []) if tt + DAY <= t and np.isfinite(v)]
        nprev[i] = len(past)
        if past:
            tr[i] = float(np.mean(past))
        hist.setdefault(a, []).append((t, h))
    G["tr"], G["nprev"] = tr, nprev
    G["grp"] = np.where(np.isnan(tr), "N", np.where(tr > 0, "P", "M"))
    G.to_pickle("s232_trades.pkl")
    rows, parts = [], []
    for p in PERS + ("все",):
        X = G if p == "все" else G[G.per == p]
        line = [p]
        for g in ("N", "P", "M"):
            Y = X[X.grp == g]; m, t, n = ct(Y.hed, Y.t); mp = ct(Y.hed - Y.pl, Y.t)[0]
            line.append(f"{g}: {n} ({n / (sum(MON.values()) if p == 'все' else MON[p]):.1f} в мес.), {m:+.2%} (t {t:+.1f}), "
                        f"сверх плацебо {mp:+.2%}")
        Y = X[X.grp.isin(["P", "M"])]
        d, td = diff(Y.hed, (Y.grp == "P").astype(float), Y.t)
        line.append(f"P − M: {d:+.2%} (t {td:+.1f})")
        if p != "все":
            parts.append(d)
        rows.append(line)
    for r in rows:
        print(" | ".join(r))
    Y = G[G.grp.isin(["P", "M"])]
    dall, tall = diff(Y.hed, (Y.grp == "P").astype(float), Y.t)
    ok = all(np.isfinite(x) and x > 0 for x in parts) and np.isfinite(tall) and tall >= 2
    print(f"гипотеза P > M: по периодам {', '.join(f'{x:+.2%}' for x in parts)}; вместе {dall:+.2%} (t {tall:+.1f}) → "
          + ("ПРОЙДЕНА" if ok else "не пройдена"))
    for lab, msk in (("опыт ≥ 10 прошлых сделок", G.nprev >= 10), ("опыт 1–9", (G.nprev >= 1) & (G.nprev < 10)),
                     ("новые (0)", G.nprev == 0)):
        X = G[msk]; m, t, n = ct(X.hed, X.t)
        print(f"  {lab}: {n} сделок, {m:+.2%} (t {t:+.1f})")
    print(f"доля сделок со списком: {np.isfinite(G.tr).mean():.0%}")


if __name__ == "__main__":
    main()
