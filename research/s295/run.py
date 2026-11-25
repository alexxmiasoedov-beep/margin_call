"""s295 — премия Кореи у монеты в час входа ⏰ (запись правил — ВЫВОДЫ.md).

π_b = C_b · m / (курс_b · C_bin) − 1 на закрытии часа 00–01 UTC (вход ⏰ в 01:00): C_b — закрытие часа в вонах на Upbit
или Bithumb, курс_b = KRW-BTC той же биржи / BTCUSDT Binance, C_bin — закрытие 15-мин свечи перпа, m — множитель тикера
(1000PEPE → 1000; выбирается тот вариант рынка и множителя, при котором |π_b| меньше, и только при |ln(1 + π_b)| < ln 1,5).
π — средняя π_b, взвешенная по обороту часа. Входы и сделки — таблицы s294 Г7 (`s294/g7_<период>.pkl`: s88 и s277).
Для отчёта: π ≥ +1 п. п. против ≤ 0 (s209), скачок π к медиане за 7 сут, изменение π за час 00–01 UTC.
Запуск: python3 -I research/s295/run.py <период> | report; признаки — /home/user/mc_data/s295/<период>.pkl."""
import os
import pickle
import re
import sys

import numpy as np
import pandas as pd

D = "/home/user/mc_data"
OUT = f"{D}/s295"
DAY, H, WEEK, BAR = 86400, 3600, 7 * 86400, 900
PER = {"2020–2022": dict(kc=f"{D}/s88/oos2020/kc", k=f"{D}/s117/k_2020.pkl", mo=24.0),
       "2022–2024": dict(kc=f"{D}/s88/oos/kc", k=f"{D}/s117/k_oos.pkl", mo=24.0),
       "2024–2026": dict(kc=None, k=f"{D}/s2/k2y.pkl", mo=24.5)}
EXS = ("upbit", "bithumb")
LIM = np.log(1.5)


class KC:
    """Часовые свечи биржи к воне: {монета: {t (открытие часа), c, v}}."""

    def __init__(self, per):
        self.kc = PER[per]["kc"]
        self.full = None if self.kc else {ex: pickle.load(open(f"{D}/s15/kr_candles_{ex}.pkl", "rb")) for ex in EXS}
        self.cache = {}

    def get(self, ex, b):
        if self.full is not None:
            return self.full[ex].get(b)
        key = (ex, b)
        if key not in self.cache:
            p = f"{self.kc}/{ex}/KRW-{b}.pkl"
            self.cache[key] = pickle.load(open(p, "rb")) if os.path.exists(p) else None
        return self.cache[key]


def at(x, hs):
    """Закрытие и оборот свечей, открытых в часы hs (NaN, если свечи нет)."""
    t = np.asarray(x["t"], np.int64)
    i = np.searchsorted(t, hs); i2 = np.minimum(i, len(t) - 1)
    ok = (i < len(t)) & (t[i2] == hs)
    c = np.where(ok, np.asarray(x["c"], float)[i2], np.nan)
    v = np.where(ok, np.asarray(x["v"], float)[i2], np.nan)
    return c, v


def bin_close(a, Ts):
    """Закрытие 15-мин свечи перпа, закрывающейся в моменты Ts."""
    t = a["t"].astype(np.int64)
    i = np.searchsorted(t, Ts - BAR); i2 = np.minimum(i, len(t) - 1)
    ok = (i < len(t)) & (t[i2] == Ts - BAR) & (a["qv"][i2] > 0)
    return np.where(ok, a["c"][i2].astype(float), np.nan)


def prem(kc, K, s, Ts):
    """π (взвешенная по обороту) в моменты Ts (закрытия часов) для перпа s; NaN — нет данных."""
    a, btc = K.get(s), K.get("BTC")
    if a is None or btc is None:
        return np.full(len(Ts), np.nan)
    Ts = np.asarray(Ts, np.int64)
    cb, bb = bin_close(a, Ts), bin_close(btc, Ts)
    m0 = re.match(r"^(1000000|100000|10000|1000)(.+)$", s)
    cands = [(s, 1.0)] + ([(m0.group(2), float(m0.group(1)))] if m0 else [])
    num = np.zeros(len(Ts)); den = np.zeros(len(Ts))
    for ex in EXS:
        kb = kc.get(ex, "BTC")
        if kb is None:
            continue
        cbtc, _ = at(kb, Ts - H)
        best = None
        for b, m in cands:
            x = kc.get(ex, b)
            if x is None:
                continue
            c, v = at(x, Ts - H)
            p = c * m / (cbtc / bb * cb) - 1
            med = np.nanmedian(np.abs(np.log1p(p))) if np.isfinite(p).any() else np.inf
            if best is None or med < best[0]:
                best = (med, p, v)
        if best is None or not np.isfinite(best[0]) or best[0] > LIM:
            continue
        _, p, v = best
        ok = np.isfinite(p) & np.isfinite(v) & (v > 0) & (np.abs(np.log1p(np.where(np.isfinite(p), p, 0))) < LIM)
        num += np.where(ok, p * v, 0.0); den += np.where(ok, v, 0.0)
    return np.where(den > 0, num / np.maximum(den, 1e-12), np.nan)


def run(per):
    X = pd.read_pickle(f"{D}/s294/g7_{per}.pkl")
    K = pickle.load(open(PER[per]["k"], "rb"))
    kc = KC(per)
    rows = []
    for s, g in X.groupby("s"):
        T = g.te.values.astype(np.int64)
        pi = prem(kc, K, s, T)
        pi0 = prem(kc, K, s, T - H)
        # скачок: π минус медиана π за 7 прошлых суток (по закрытиям часов)
        hist = []
        for t0 in T:
            hs = t0 - H * np.arange(1, 169)
            v = prem(kc, K, s, hs)
            hist.append(np.nanmedian(v) if np.isfinite(v).sum() >= 48 else np.nan)
        for i, a, b, c in zip(g.index, pi, pi0, hist):
            rows.append(dict(i=i, pi=a, dpi=a - b, jump=a - c))
    F = pd.DataFrame(rows).set_index("i").sort_index()
    X = X.join(F)
    os.makedirs(OUT, exist_ok=True)
    X.to_pickle(f"{OUT}/{per}.pkl")
    print(f"{per}: входов {len(X)}, с премией {X.pi.notna().sum()}; π медиана {X.pi.median():+.2%}, 10–90% "
          f"{X.pi.quantile(.1):+.2%}…{X.pi.quantile(.9):+.2%}", flush=True)


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


def combine(ms, ses):
    w = np.array([1 / s ** 2 for s in ses])
    m = float(np.sum(w * np.array(ms)) / w.sum())
    return m, m * np.sqrt(w.sum())


def split_line(P, R, col, ex, lab, split=None):
    ms, ses, sg, cells = [], [], [], []
    for per, X in R.items():
        Y = X[X[col].notna() & X[ex].notna()]
        if split is None:
            q1, q2 = Y[col].quantile([1 / 3, 2 / 3])
            A, B = Y[Y[col] > q2], Y[Y[col] <= q1]
        else:
            A, B = Y[Y[col] >= split[0]], Y[Y[col] <= split[1]]
        m1, _, n1, s1 = ct(A[ex], A.te); m2, _, n2, s2 = ct(B[ex], B.te)
        d, se = m1 - m2, np.hypot(s1, s2)
        ms.append(d); ses.append(se); sg.append(d < 0)
        cells.append(f"{per}: верх {m1:+.2%} (n {n1}) против низа {m2:+.2%} (n {n2}), Δ {d:+.2%} (t {d / se:+.1f})")
    m, t = combine(ms, ses)
    P(f"  {lab}: вместе Δ {m:+.2%} (t {t:+.1f}); Δ < 0 во всех — {'да' if all(sg) else 'нет'}")
    for c in cells:
        P(f"    {c}")


def report():
    R = {p: pd.read_pickle(f"{OUT}/{p}.pkl") for p in PER}
    L = []
    P = lambda s="": (print(s), L.append(s))  # noqa: E731
    P("s295 — премия Кореи у монеты сверх BTC в час входа ⏰ (01:00 UTC)")
    for per, X in R.items():
        P(f"  {per}: входов {len(X)}, с премией {X.pi.notna().sum()}; π медиана {X.pi.median():+.2%}, доля π ≥ +1 п. п. "
          f"{(X.pi >= 0.01).mean():.0%}, π ≤ 0 {(X.pi <= 0).mean():.0%}")
    P(); P("== π, трети (основной признак) ==")
    for ex, lab in (("S_10_25", "10/25/48 (основной)"), ("h24_net", "24 ч, стоп 10%"), ("h8_net", "8 ч, стоп 10%"),
                    ("h24_hed", "24 ч, с хеджем альтов")):
        split_line(P, R, "pi", ex, lab)
    P(); P("== s209: π ≥ +1 п. п. против π ≤ 0 ==")
    for ex, lab in (("S_10_25", "10/25/48"), ("h24_net", "24 ч")):
        split_line(P, R, "pi", ex, lab, split=(0.01, 0.0))
    P(); P("== скачок π к медиане за 7 сут, трети ==")
    for ex, lab in (("S_10_25", "10/25/48"), ("h24_net", "24 ч")):
        split_line(P, R, "jump", ex, lab)
    P(); P("== изменение π за час 00–01 UTC, трети ==")
    for ex, lab in (("S_10_25", "10/25/48"), ("h24_net", "24 ч")):
        split_line(P, R, "dpi", ex, lab)
    old = pd.concat([R["2020–2022"], R["2022–2024"]])
    thr = float(old.pi.quantile(2 / 3))
    P(); P(f"== двойник «⏰ при π < {thr:+.2%}» (67-й перцентиль π входов 2020–2024 гг.; без π — вход) ==")
    for per, X in R.items():
        keep = ~(X.pi >= thr)
        for ex, pl_col, lab in (("S_10_25", "pl_S_10_25", "10/25/48"), ("h24_net", "h24_pl", "24 ч")):
            A = X[keep & X[ex].notna()]; B = X[X[ex].notna()]
            ma, ta, na, _ = ct(A[ex], A.te); mb, tb_, nb, _ = ct(B[ex], B.te)
            med = A.te.median()
            h1, h2 = A[A.te <= med][ex].mean(), A[A.te > med][ex].mean()
            mp, tp, _, _ = ct(A[ex] - A[pl_col], A.te)
            P(f"  {per} {lab}: двойник {ma:+.2%} (t {ta:+.1f}, {na / PER[per]['mo']:.1f} в мес., половины {h1:+.2%} / {h2:+.2%}, "
              f"сверх плацебо {mp:+.2%} t {tp:+.1f}) против ⏰ {mb:+.2%} (t {tb_:+.1f}, {nb / PER[per]['mo']:.1f} в мес.)")
    open(f"{OUT}/report.txt", "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
