"""s298 — гипотезы s297: «Корея ведёт» (Г1) и «внимание уже уходит» (Г2) на ⏰ и 🇰🇷 (запись правил — ВЫВОДЫ.md).

Признаки — s297/feat.pkl. Сделки ⏰ — s294/g7_<период>.pkl (10/25/48 и плацебо — s88; 24 ч и 8 ч — s277), 🇰🇷 — выходы
журнала 10/25/48 (s118, s119, s49) и 8 ч / 24 ч (s277). Запуск: python3 -I research/s298/run.py → s298_report.txt."""
import importlib.util

import numpy as np
import pandas as pd

D = "/home/user/mc_data"
PERS = ("2020–2022", "2022–2024", "2024–2026")
MO = {"2020–2022": 24.0, "2022–2024": 24.0, "2024–2026": 24.5}
NATIVE = {"2020–2022": ["/home/user/mc_2020/s118_kr.pkl"], "2022–2024": ["/home/user/mc_oos/s119_old.pkl"],
          "2024–2026": [f"{D}/s49/trades.pkl"]}
spec = importlib.util.spec_from_file_location("s295", "/home/user/margin_call/research/s295/run.py")
S295 = importlib.util.module_from_spec(spec); spec.loader.exec_module(S295)
ct, combine = S295.ct, S295.combine


def tables():
    F = pd.read_pickle(f"{D}/s297/feat.pkl")
    F["vl15"] = [r.get(f"{r['kr']}_vl15", np.nan) if isinstance(r["kr"], str) else np.nan for _, r in F.iterrows()]
    F["fade"] = [r.get(f"{r['kr']}_fade", np.nan) if isinstance(r["kr"], str) else np.nan for _, r in F.iterrows()]
    F = F[["j", "per", "s", "te", "lead", "vl15", "fade"]]
    T = {}
    for per in PERS:
        g = pd.read_pickle(f"{D}/s294/g7_{per}.pkl")
        g = g.rename(columns={"S_10_25": "main", "pl_S_10_25": "pl_main"})
        T[("⏰", per)] = g.merge(F[(F.j == "⏰") & (F.per == per)], on=["s", "te"], how="left")
        R = pd.read_pickle(f"{D}/s277_{per}.pkl")
        k = R[(R.h == "🇰🇷") & (R.ex == "8 ч")][["s", "te", "net", "hed", "pl", "stop"]].rename(
            columns={"net": "h8_net", "hed": "h8_hed", "pl": "h8_pl", "stop": "h8_stop"})
        k24 = R[(R.h == "🇰🇷") & (R.ex == "24 ч")][["s", "te", "net", "hed"]].rename(columns={"net": "h24_net", "hed": "h24_hed"})
        k = k.merge(k24, on=["s", "te"], how="left")
        nat = pd.concat([pd.read_pickle(f)[["s", "t", "net"] + (["pl"] if "pl" in pd.read_pickle(f).columns else [])] for f in NATIVE[per]])
        nat["s"] = [v[:-4] if v.endswith("USDT") else v for v in nat.s.astype(str)]
        nat["te"] = nat.t.astype(float).astype(np.int64)
        nat = nat.drop_duplicates(["s", "te"]).rename(columns={"net": "main", "pl": "pl_main"})[["s", "te", "main"] + (["pl_main"] if "pl_main" in nat else [])]
        k["s"] = k.s.astype(str); k["te"] = k.te.astype(np.int64)
        k = k.merge(nat, on=["s", "te"], how="left")
        T[("🇰🇷", per)] = k.merge(F[(F.j == "🇰🇷") & (F.per == per)], on=["s", "te"], how="left")
    return T


def two(A, B, ex):
    m1, _, n1, s1 = ct(A[ex], A.te); m2, _, n2, s2 = ct(B[ex], B.te)
    return m1 - m2, np.hypot(s1, s2), m1, n1, m2, n2


def main():
    T = tables()
    L = []
    P = lambda s="": (print(s), L.append(s))  # noqa: E731
    P("s298 — гипотезы s297 на ⏰ и 🇰🇷 (основной выход — журнал 10/25/48)")
    for (j, per), X in T.items():
        P(f"  {j} {per}: входов {len(X)}, с основной сделкой {X.main.notna().sum()}, с lead {X.lead.notna().sum()}, "
          f"Корея ведёт {(X.lead <= -2).sum()} ({(X.lead <= -2).sum() / MO[per]:.1f} в мес.), с vl15 {X.vl15.notna().sum()}")
    P(); P("== Г1 «Корея ведёт» (lead ≤ −2 мин) против остальных ==")
    for ex, lab in (("main", "10/25/48 (основной)"), ("h24_net", "24 ч"), ("h8_net", "8 ч"), ("h24_hed", "24 ч с хеджем")):
        ms, ses, sg, cells = [], [], [], []
        for j in ("⏰", "🇰🇷"):
            for per in PERS:
                X = T[(j, per)]; Y = X[X.lead.notna() & X[ex].notna()]
                d, se, m1, n1, m2, n2 = two(Y[Y.lead <= -2], Y[Y.lead > -2], ex)
                ms.append(d); ses.append(se); sg.append(d > 0)
                cells.append(f"{j} {per}: ведёт {m1:+.2%} (n {n1}) против {m2:+.2%} (n {n2}), Δ {d:+.2%} (t {d / se:+.1f})")
        m, t = combine(ms, ses)
        P(f"  {lab}: вместе Δ {m:+.2%} (t {t:+.1f}); Δ > 0 во всех шести — {'да' if all(sg) else 'нет'}")
        for c in cells:
            P(f"    {c}")
    P(); P("== Г2 «внимание уже уходит» (⏰): нижняя треть vl15 − верхняя ==")
    for ex, lab in (("main", "10/25/48 (основной)"), ("h24_net", "24 ч"), ("h8_net", "8 ч"), ("h24_hed", "24 ч с хеджем")):
        ms, ses, sg, cells = [], [], [], []
        for per in PERS:
            X = T[("⏰", per)]; Y = X[X.vl15.notna() & X[ex].notna()]
            q1, q2 = Y.vl15.quantile([1 / 3, 2 / 3])
            d, se, m1, n1, m2, n2 = two(Y[Y.vl15 <= q1], Y[Y.vl15 > q2], ex)
            ms.append(d); ses.append(se); sg.append(d > 0)
            cells.append(f"{per}: низ {m1:+.2%} (n {n1}) против верха {m2:+.2%} (n {n2}), Δ {d:+.2%} (t {d / se:+.1f})")
        m, t = combine(ms, ses)
        P(f"  {lab}: вместе Δ {m:+.2%} (t {t:+.1f}); Δ > 0 во всех — {'да' if all(sg) else 'нет'}")
        for c in cells:
            P(f"    {c}")
    old = pd.concat([T[("⏰", "2020–2022")], T[("⏰", "2022–2024")]])
    thr = float(old.vl15.quantile(2 / 3))
    P(); P(f"== двойник «⏰ при vl15 < {thr:.3f}» (67-й перцентиль 2020–2024 гг.; без признака — вход) ==")
    for per in PERS:
        X = T[("⏰", per)]
        keep = ~(X.vl15 >= thr)
        A = X[keep & X.main.notna()]; B = X[X.main.notna()]
        ma, ta, na, _ = ct(A.main, A.te); mb, tb_, nb, _ = ct(B.main, B.te)
        med = A.te.median()
        mp, tp, _, _ = ct(A.main - A.pl_main, A.te)
        P(f"  {per}: двойник {ma:+.2%} (t {ta:+.1f}, {na / MO[per]:.1f} в мес., половины {A[A.te <= med].main.mean():+.2%} / "
          f"{A[A.te > med].main.mean():+.2%}, сверх плацебо {mp:+.2%} t {tp:+.1f}) против ⏰ {mb:+.2%} (t {tb_:+.1f})")
    P(); P("== для отчёта: Г3 (⏰, трети «цена Upbit в 01:00 ниже максимума окна»: глубже − мельче) и «перп ведёт» ==")
    for per in PERS:
        X = T[("⏰", per)]; Y = X[X.fade.notna() & X.main.notna()]
        q1, q2 = Y.fade.quantile([1 / 3, 2 / 3])
        d, se, m1, n1, m2, n2 = two(Y[Y.fade <= q1], Y[Y.fade > q2], "main")
        P(f"  Г3 ⏰ {per}: глубже {m1:+.2%} против мельче {m2:+.2%}, Δ {d:+.2%} (t {d / se:+.1f})")
    for j in ("⏰", "🇰🇷"):
        for per in PERS:
            X = T[(j, per)]; Y = X[X.lead.notna() & X.main.notna()]
            d, se, m1, n1, m2, n2 = two(Y[Y.lead >= 2], Y[Y.lead < 2], "main")
            P(f"  перп ведёт {j} {per}: {m1:+.2%} (n {n1}) против {m2:+.2%} (n {n2}), Δ {d:+.2%} (t {d / se:+.1f})")
    open(f"{D}/s298_report.txt", "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
