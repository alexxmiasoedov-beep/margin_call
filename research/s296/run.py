"""s296 — премия Кореи на входе и шорт 8 ч: проверка наблюдения s295 на 🇰🇷, 🔝, 👀 (запись правил — ВЫВОДЫ.md).

🇰🇷 — премия по минутным свечам Upbit и Bithumb на момент входа (`fetch.py` → s296/kr_min.jsonl), 🔝 и 👀 — по часовым
свечам s15 (функции s295). Сделки — s277 (8 ч и 24 ч со стопом 10%, хедж альтов). Входы с ⏰ той же монеты ближе 24 ч
в основной проверке не участвуют. Запуск: python3 -I research/s296/run.py; сводка — /home/user/mc_data/s296/report.txt."""
import importlib.util
import json
import pickle

import numpy as np
import pandas as pd

D = "/home/user/mc_data"
OUT = f"{D}/s296"
PERS = ("2020–2022", "2022–2024", "2024–2026")
KF = {"2020–2022": f"{D}/s117/k_2020.pkl", "2022–2024": f"{D}/s117/k_oos.pkl", "2024–2026": f"{D}/s2/k2y.pkl"}
MO = {"2020–2022": 24.0, "2022–2024": 24.0, "2024–2026": 24.5}
LIM = np.log(1.5)
spec = importlib.util.spec_from_file_location("s295", "/home/user/margin_call/research/s295/run.py")
S295 = importlib.util.module_from_spec(spec); spec.loader.exec_module(S295)
ct, combine = S295.ct, S295.combine


def trades(per):
    R = pd.read_pickle(f"{D}/s277_{per}.pkl")
    out = {}
    o9 = R[(R.h == "⏰") & (R.ex == "8 ч")]
    for h in ("🇰🇷", "🔝", "👀", "⏰"):
        a = R[(R.h == h) & (R.ex == "8 ч")][["s", "te", "net", "hed", "pl", "stop"]]
        b = R[(R.h == h) & (R.ex == "24 ч")][["s", "te", "net", "hed"]].rename(columns={"net": "net24", "hed": "hed24"})
        if not len(a):
            continue
        a = a.merge(b, on=["s", "te"], how="left")
        a["s"] = a.s.astype(str); a["te"] = a.te.astype(np.int64)
        ov = []
        for s, te in zip(a.s, a.te):
            t = o9.te[o9.s == s].values
            ov.append(bool(len(t) and (np.abs(t - te) <= 86400).any()))
        a["ov9"] = ov if h != "⏰" else False
        out[h] = a.reset_index(drop=True)
    return out


def kr_prem(per, X, K):
    M = {}
    for ln in open(f"{OUT}/kr_min.jsonl"):
        d = json.loads(ln)
        if d["per"] == per and "err" not in d:
            M[(d["s"], d["te"])] = d
    btc = K["BTC"]
    pis = []
    for s, te in zip(X.s, X.te):
        d = M.get((s, int(te)))
        a = K.get(s)
        if d is None or a is None:
            pis.append(np.nan); continue
        cb = S295.bin_close(a, np.array([te]))[0]; bb = S295.bin_close(btc, np.array([te]))[0]
        num = den = 0.0
        for ex in ("upbit", "bithumb"):
            e = d.get(ex)
            if not e or not e.get("btc") or not e.get("coin"):
                continue
            bst, bk = e["btc"]
            if te - (bst + 60) > 120 or not (cb == cb and bb == bb):
                continue
            best = None
            for c in e["coin"]:
                if te - (c["st"] + 60) > 600 or c["v60"] <= 0:
                    continue
                p = c["c"] * c["m"] / (bk / bb * cb) - 1
                if abs(np.log1p(p)) < LIM and (best is None or abs(np.log1p(p)) < abs(np.log1p(best[0]))):
                    best = (p, c["v60"])
            if best:
                num += best[0] * best[1]; den += best[1]
        pis.append(num / den if den > 0 else np.nan)
    return np.array(pis)


def delta(Y, col, ex):
    Y = Y[Y[col].notna() & Y[ex].notna()]
    q1, q2 = Y[col].quantile([1 / 3, 2 / 3])
    A, B = Y[Y[col] > q2], Y[Y[col] <= q1]
    m1, _, n1, s1 = ct(A[ex], A.te); m2, _, n2, s2 = ct(B[ex], B.te)
    return m1 - m2, np.hypot(s1, s2), m1, n1, m2, n2


def main():
    L = []
    P = lambda s="": (print(s), L.append(s))  # noqa: E731
    T = {}
    for per in PERS:
        tr = trades(per)
        K = pickle.load(open(KF[per], "rb"))
        X = tr["🇰🇷"]
        X["pi"] = kr_prem(per, X, K)
        T[(per, "🇰🇷")] = X
        if per == "2024–2026":
            kc = S295.KC(per)
            for h in ("🔝", "👀"):
                Y = tr[h]
                Y["pi"] = np.nan
                for s, g in Y.groupby("s"):
                    Y.loc[g.index, "pi"] = S295.prem(kc, K, s, g.te.values.astype(np.int64))
                T[(per, h)] = Y
        del K
    P("s296 — премия Кореи сверх BTC на входе и шорт 8 ч (стоп 10%); Δ = верхняя треть π − нижняя")
    for (per, h), X in T.items():
        P(f"  {per} {h}: входов {len(X)}, без ⏰ рядом {(~X.ov9).sum()}, с π {X.pi.notna().sum()} "
          f"(без ⏰ — {(X.pi.notna() & ~X.ov9).sum()}); π медиана {X.pi.median():+.2%}")
    P(); P("== 🇰🇷 без ⏰ рядом (основная проверка) ==")
    for ex, lab in (("net", "8 ч (основной)"), ("hed", "8 ч с хеджем альтов"), ("net24", "24 ч"), ("hed24", "24 ч с хеджем")):
        ms, ses, sg, cells = [], [], [], []
        for per in PERS:
            X = T[(per, "🇰🇷")]
            d, se, m1, n1, m2, n2 = delta(X[~X.ov9], "pi", ex)
            ms.append(d); ses.append(se); sg.append(d < 0)
            cells.append(f"{per}: верх {m1:+.2%} (n {n1}) против низа {m2:+.2%} (n {n2}), Δ {d:+.2%} (t {d / se:+.1f})")
        m, t = combine(ms, ses)
        P(f"  {lab}: вместе Δ {m:+.2%} (t {t:+.1f}); Δ < 0 во всех — {'да' if all(sg) else 'нет'}")
        for c in cells:
            P(f"    {c}")
    P(); P("== 🔝 и 👀 без ⏰ рядом, 2024–2026 гг. ==")
    tk = T[("2024–2026", "🔝")]; rt = T[("2024–2026", "👀")]
    both = pd.concat([tk[~tk.ov9], rt[~rt.ov9]]).drop_duplicates(["s", "te"])
    for nm, Y in (("вместе (основная)", both), ("🔝", tk[~tk.ov9]), ("👀", rt[~rt.ov9])):
        for ex, lab in (("net", "8 ч"), ("hed", "8 ч с хеджем"), ("net24", "24 ч")):
            d, se, m1, n1, m2, n2 = delta(Y, "pi", ex)
            P(f"  {nm}, {lab}: верх {m1:+.2%} (n {n1}) против низа {m2:+.2%} (n {n2}), Δ {d:+.2%} (t {d / se:+.1f})")
    P(); P("== 🇰🇷 со всеми входами (с пересечениями с ⏰), 8 ч ==")
    for per in PERS:
        d, se, m1, n1, m2, n2 = delta(T[(per, "🇰🇷")], "pi", "net")
        P(f"  {per}: Δ {d:+.2%} (t {d / se:+.1f}, n {n1}/{n2})")
    pd.to_pickle(T, f"{OUT}/tables.pkl")
    open(f"{OUT}/report.txt", "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
