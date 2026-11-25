"""s294 Г8 — раздача в свече пампа (запись правил — ВЫВОДЫ.md). Признаки ленты — g8_fetch.py (s294/g8_feat.jsonl).

M_q = (крупные тейкер-продажи − крупные тейкер-покупки) / оборот свечи пампа на перпе и споте; «крупная» — заявка
≥ q-квантиля сумм заявок своей площадки в свече. q выбирается на 2020–2022 гг. по Δ = верхняя треть M − остальные
(шорт 8 ч, стоп 10%, 🛒 и 🇰🇷 вместе, памп обоих журналов один раз); проверка — 2022–2024 и 2024–2026 гг.
Для отчёта: окно 2 ч, доля мелких покупок, только перп, только спот, журналы отдельно, выходы журналов 10/25/48,
хедж индексом альтов. Проверка ленты: оборот перпа по aggTrades против qv свечи пампа.
Запуск: python3 -I research/s294/g8.py [check]; сводка — /home/user/mc_data/s294/g8_report.txt"""
import pickle
import sys

import numpy as np
import pandas as pd

D = "/home/user/mc_data"
OUT = f"{D}/s294"
PERS = ("2020–2022", "2022–2024", "2024–2026")
QS = (0.9, 0.98, 0.995)
WEEK = 7 * 86400
MO = {"2020–2022": 24.0, "2022–2024": 24.0, "2024–2026": 24.5}
NATIVE = {"2020–2022": ["/home/user/mc_2020/s119_y2020.pkl", "/home/user/mc_2020/s118_kr.pkl"],
          "2022–2024": ["/home/user/mc_oos/s119_old.pkl"], "2024–2026": [f"{D}/s49/trades.pkl"]}
KF = {"2020–2022": f"{D}/s117/k_2020.pkl", "2022–2024": f"{D}/s117/k_oos.pkl", "2024–2026": f"{D}/s2/k2y.pkl"}


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


def load():
    F = pd.read_json(f"{OUT}/g8_feat.jsonl", lines=True, dtype={"s": str})
    F = F.drop_duplicates(["per", "s", "te"], keep="last")
    out = []
    for per in PERS:
        a = pd.read_pickle(f"{D}/s270_{per}.pkl")
        a = a[(a.grp == "S") & (a.side == -1) & (a.sl == 0.1) & (a.hold == 8)][["s", "te", "net", "stop", "hed", "pl"]].assign(j="🛒")
        b = pd.read_pickle(f"{D}/s277_{per}.pkl")
        b = b[(b.h == "🇰🇷") & (b.ex == "8 ч")][["s", "te", "net", "stop", "hed", "pl"]].assign(j="🇰🇷")
        u = pd.concat([a, b])
        u["s"] = u.s.astype(str); u["te"] = u.te.astype(np.int64)
        g = u.groupby(["s", "te"]).agg(net=("net", "first"), stop=("stop", "first"), hed=("hed", "first"), pl=("pl", "first"),
                                       j=("j", lambda v: "".join(sorted(set(v))))).reset_index()
        nat = pd.concat([pd.read_pickle(f)[["s", "t", "net"]] for f in NATIVE[per]])
        nat["s"] = [v[:-4] if v.endswith("USDT") else v for v in nat.s.astype(str)]
        nat["te"] = nat.t.astype(float).astype(np.int64)
        nat = nat.drop_duplicates(["s", "te"])[["s", "te", "net"]].rename(columns={"net": "nat"})
        g = g.merge(nat, on=["s", "te"], how="left")
        g["per"] = per
        out.append(g)
    X = pd.concat(out).merge(F, on=["per", "s", "te"], how="left")
    for c in [c for c in X.columns if c[:2] in ("SA", "SB")]:
        X[c] = X[c].fillna(0.0)
    for w in ("A", "B"):
        V = X[f"F{w}_V"] + X[f"S{w}_V"]
        X[f"V{w}"] = V
        for q in QS:
            X[f"M{w}{q}"] = (X[f"F{w}_bs{q}"] + X[f"S{w}_bs{q}"] - X[f"F{w}_bb{q}"] - X[f"S{w}_bb{q}"]) / V
            X[f"MF{w}{q}"] = (X[f"F{w}_bs{q}"] - X[f"F{w}_bb{q}"]) / X[f"F{w}_V"]
            X[f"MS{w}{q}"] = np.where(X[f"S{w}_V"] > 0, (X[f"S{w}_bs{q}"] - X[f"S{w}_bb{q}"]) / X[f"S{w}_V"].where(X[f"S{w}_V"] > 0), np.nan)
        X[f"SB{w}"] = (X[f"F{w}_sb"] + X[f"S{w}_sb"]) / V
    return X


def top_rest(X, col, ex, frac=2 / 3):
    Y = X[X[col].notna() & X[ex].notna()]
    q = Y[col].quantile(frac)
    A, B = Y[Y[col] > q], Y[Y[col] <= q]
    m1, _, n1, s1 = ct(A[ex], A.te); m2, _, n2, s2 = ct(B[ex], B.te)
    d, se = m1 - m2, np.hypot(s1, s2)
    return d, se, m1, n1, m2, n2


def check():
    X = load()
    for per in PERS:
        K = pickle.load(open(KF[per], "rb"))
        Y = X[(X.per == per) & X.FA_V.notna()]
        r = []
        for s, te, v in zip(Y.s, Y.te, Y.FA_V):
            a = K.get(s)
            if a is None:
                continue
            i = int(np.searchsorted(a["t"], te - 900))
            if i < len(a["t"]) and a["t"][i] == te - 900 and a["qv"][i] > 0:
                r.append(v / float(a["qv"][i]))
        r = np.array(r)
        print(f"{per}: оборот перпа по ленте / qv свечи — медиана {np.median(r):.4f}, 1–99% {np.quantile(r, .01):.3f}…{np.quantile(r, .99):.3f}, n {len(r)}", flush=True)
        del K


def report():
    X = load()
    L = []
    P = lambda s="": (print(s), L.append(s))  # noqa: E731
    P("s294 Г8 — раздача в свече пампа: M = (крупные тейкер-продажи − крупные покупки) / оборот, перп + спот")
    for per in PERS:
        Y = X[X.per == per]
        P(f"  {per}: пампов {len(Y)} (🛒 {Y.j.str.contains('🛒').sum()}, 🇰🇷 {Y.j.str.contains('🇰🇷').sum()}), с лентой "
          f"{Y.FA_V.notna().sum()}, со спотом {(Y.SA_V > 0).sum()}, ошибок {Y.err.notna().sum() if 'err' in Y else 0}")
    P(); P("== выбор q на 2020–2022 гг. (шорт 8 ч, стоп 10%; Δ = верхняя треть − остальные) ==")
    Y = X[X.per == "2020–2022"]
    best, bd = None, -1e9
    for q in QS:
        d, se, m1, n1, m2, n2 = top_rest(Y, f"MA{q}", "net")
        P(f"  q {q}: верх {m1:+.2%} (n {n1}) против {m2:+.2%} (n {n2}), Δ {d:+.2%} (t {d / se:+.1f})")
        if d > bd:
            best, bd = q, d
    P(f"  выбран q = {best}")
    P(); P(f"== проверка с q = {best} ==")
    rows = [("MA", "основной: свеча пампа, перп + спот", "net"), ("MA", "то же, с хеджем альтов", "hed"),
            ("MA", "то же, выходы журналов 10/25/48", "nat"), ("MB", "окно 2 ч", "net"), ("MFA", "только перп", "net"),
            ("MSA", "только спот", "net")]
    for pre, lab, ex in rows:
        col = f"{pre}{best}"
        ms, ses, sg, cells = [], [], [], []
        for per in PERS:
            d, se, m1, n1, m2, n2 = top_rest(X[X.per == per], col, ex)
            cells.append(f"{per}: верх {m1:+.2%} (n {n1}) против {m2:+.2%} (n {n2}), Δ {d:+.2%} (t {d / se:+.1f})")
            if per != "2020–2022":
                ms.append(d); ses.append(se); sg.append(d > 0)
        m, t = combine(ms, ses)
        P(f"  {lab}: 2022–2026 вместе Δ {m:+.2%} (t {t:+.1f}); Δ > 0 в обоих — {'да' if all(sg) else 'нет'}")
        for c in cells:
            P(f"    {c}")
    P(); P("== журналы отдельно (свеча пампа, перп + спот, шорт 8 ч) ==")
    for jj in ("🛒", "🇰🇷"):
        cells = []
        for per in PERS:
            d, se, m1, n1, m2, n2 = top_rest(X[(X.per == per) & X.j.str.contains(jj)], f"MA{best}", "net")
            cells.append(f"{per} Δ {d:+.2%} (t {d / se:+.1f}, n {n1}/{n2})")
        P(f"  {jj}: " + "; ".join(cells))
    P(); P("== доля мелких покупок (заявки ≤ медианы) в обороте свечи, верхняя треть − остальные ==")
    for per in PERS:
        d, se, m1, n1, m2, n2 = top_rest(X[X.per == per], "SBA", "net")
        P(f"  {per}: верх {m1:+.2%} против {m2:+.2%}, Δ {d:+.2%} (t {d / se:+.1f})")
    P(); P("== трети M (основной признак), средний доход шорта 8 ч ==")
    for per in PERS:
        Y = X[(X.per == per) & X[f"MA{best}"].notna()]
        q1, q2 = Y[f"MA{best}"].quantile([1 / 3, 2 / 3])
        g = [Y[Y[f"MA{best}"] <= q1], Y[(Y[f"MA{best}"] > q1) & (Y[f"MA{best}"] <= q2)], Y[Y[f"MA{best}"] > q2]]
        P(f"  {per}: границы {q1:+.3f} / {q2:+.3f}; низ {g[0].net.mean():+.2%}, сер. {g[1].net.mean():+.2%}, верх {g[2].net.mean():+.2%}; "
          f"стопов {g[0].stop.mean():.0%} / {g[1].stop.mean():.0%} / {g[2].stop.mean():.0%}")
    open(f"{OUT}/g8_report.txt", "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    check() if len(sys.argv) > 1 and sys.argv[1] == "check" else report()
