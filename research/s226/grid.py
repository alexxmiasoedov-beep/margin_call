"""s226 — явный перебор сочетаний параметров вокруг событий займа (метод и пороги — ВЫВОДЫ.md, записаны до расчёта).

17 групп, 71 условие; правило — до четырёх условий из разных групп (одиночные, пары, тройки, четвёрки — все). Для каждого
срока шорта (s4, s24, s48, s168, без хеджа):
1. A — сочетания с ≥ 100 событиями и средним > 0, 5000 лучших по t (кластеры — недели);
2. B — ≥ 100 событий, среднее > 0, t ≥ 2;
3. выбор до просмотра C — наибольший min(t A, t B); в отчёт — 10 лучших;
4. выбранное — честными сделками (одна сделка на монету до выхода) на всём периоде и на C, плацебо той же монеты;
5. контроль — шаги 1–3 на доходах, перемешанных внутри месяца (3 прогона).
Запуск из /home/user/mc_data после events.py: python3 <repo>/research/s226/grid.py [срок …] [shuffle]"""
import itertools
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s216", "s187"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from bombe import zclust  # noqa: E402

DAY, WEEK = 86400, 7 * 86400
TA = pd.Timestamp("2025-10-01", tz="UTC").timestamp(); TB = pd.Timestamp("2026-04-01", tz="UTC").timestamp()
T_END = pd.Timestamp("2026-10-19", tz="UTC").timestamp(); T_BEG = pd.Timestamp("2025-02-20", tz="UTC").timestamp()
MID = (T_BEG + T_END) / 2
PAR = {"s4": (0.10, 4), "s24": (0.25, 24), "s48": (0.25, 48), "s168": (0.50, 168)}
HED = {"s4": "y_hs4", "s24": "y_hs24", "s48": "y_hs48", "s168": "y_hs168"}
MINA, MINB, TOPA, ZB = 100, 100, 5000, 2.0

# (группа, подпись, признак, знак, порог) — ровно как в записи до расчёта
GROUPS = [
    ("тип события", [("новый займ", "ev", "eq", 1), ("займ вырос", "ev", "eq", 2)]),
    ("займ за 24 ч", [(f"займ ≥ {v / 1e6:g} млн $", "bor", "ge", v) for v in (1e5, 3e5, 1e6, 3e6, 1e7)]),
    ("займ к обороту", [(f"займ / оборот ≥ {v:.0%}", "bqv", "ge", v) for v in (0.02, 0.05, 0.10, 0.20, 0.50)]),
    # уточнение до расчёта доходов: доля отдачи в канале не бывает выше 0,35, пороги 0,5 и 1 пусты → 0,25 и 0,3
    ("отдача", [("отдача / займ ≤ 0,1", "rb", "le", 0.1), ("отдача / займ ≥ 0,25", "rb", "ge", 0.25),
                ("отдача / займ ≥ 0,3", "rb", "ge", 0.3)]),
    ("стоимость и лимит", [(f"ставка / 10-й перц. ≥ {v:g}", "ux", "ge", v) for v in (1.5, 2.0, 3.0)]
     + [("пул выбран", "lim", "eq", 1)]),
    # уточнение: в pres7 входит и час события, поэтому «0 ч за 7 сут до события» — pres7 ≤ 1
    ("удержание", [("за 7 сут в канале 0 ч до события", "pres7", "le", 1), ("за 7 сут в канале ≥ 24 ч", "pres7", "ge", 24),
                   ("за 7 сут в канале ≥ 72 ч", "pres7", "ge", 72), ("подряд в канале ≥ 24 ч", "run", "ge", 24),
                   ("подряд в канале ≥ 72 ч", "run", "ge", 72)]),
    ("цена 4 ч", [(f"цена 4 ч ≥ +{v:.0%}", "r4", "ge", v) for v in (0.03, 0.05, 0.10)]
     + [(f"цена 4 ч ≤ −{v:.0%}", "r4", "le", -v) for v in (0.03, 0.05)]),
    ("цена 24 ч", [(f"цена 24 ч ≥ +{v:.0%}", "r24", "ge", v) for v in (0.05, 0.10, 0.20, 0.30)]
     + [(f"цена 24 ч ≤ −{v:.0%}", "r24", "le", -v) for v in (0.05, 0.10, 0.20)]),
    ("цена 72 ч", [(f"цена 72 ч ≥ +{v:.0%}", "r72", "ge", v) for v in (0.20, 0.50)] + [("цена 72 ч ≤ −20%", "r72", "le", -0.20)]),
    ("OI 4 ч", [(f"OI 4 ч ≥ +{v:.0%}", "doi4", "ge", v) for v in (0.03, 0.05, 0.10)]
     + [(f"OI 4 ч ≤ −{v:.0%}", "doi4", "le", -v) for v in (0.03, 0.05)]),
    ("OI 24 ч", [(f"OI 24 ч ≥ +{v:.0%}", "doi24", "ge", v) for v in (0.10, 0.20, 0.50)]
     + [(f"OI 24 ч ≤ −{v:.0%}", "doi24", "le", -v) for v in (0.10, 0.20)]),
    ("фандинг", [("фандинг < 0", "f8", "lt", 0.0), ("фандинг ≤ −0,03%", "f8", "le", -0.0003),
                 ("фандинг ≤ −0,1%", "f8", "le", -0.001), ("фандинг ≤ −0,3%", "f8", "le", -0.003),
                 ("фандинг выше базовых +0,01%", "f8", "gt", 0.000105), ("фандинг ≥ +0,03%", "f8", "ge", 0.0003)]),
    ("оборот", [(f"оборот 24 ч / 7 сут ≥ {v:g}", "qvx", "ge", v) for v in (1.5, 2.0, 3.0, 5.0)]
     + [("оборот 24 ч / 7 сут ≤ 0,7", "qvx", "le", 0.7)]),
    ("лонг/шорт счетов", [("лонг/шорт ≥ 2", "lsr_acc", "ge", 2.0), ("лонг/шорт ≥ 3", "lsr_acc", "ge", 3.0),
                          ("лонг/шорт ≤ 1", "lsr_acc", "le", 1.0)]),
    ("изменение лонг/шорт", [("лонг/шорт за сутки ≥ +0,2", "dlsr24", "ge", 0.2), ("лонг/шорт за сутки ≥ +0,5", "dlsr24", "ge", 0.5),
                             ("лонг/шорт за сутки ≤ −0,2", "dlsr24", "le", -0.2), ("лонг/шорт за сутки ≤ −0,5", "dlsr24", "le", -0.5)]),
    ("покупки 4 ч", [("покупки 4 ч ≥ 55%", "tb4", "ge", 0.55), ("покупки 4 ч ≤ 45%", "tb4", "le", 0.45)]),
    ("BTC 24 ч", [("BTC 24 ч ≥ +2%", "btc24", "ge", 0.02), ("BTC 24 ч ≤ −2%", "btc24", "le", -0.02)]),
]


def masks(X):
    M, names, fam = [], [], []
    for g, (_, conds) in enumerate(GROUPS):
        for nm, f, op, v in conds:
            x = X[f].to_numpy(float)
            m = {"ge": x >= v, "le": x <= v, "lt": x < v, "gt": x > v, "eq": x == v}[op] & np.isfinite(x)
            M.append(m); names.append(nm); fam.append(g)
    M.append(np.ones(len(X), bool))                               # пустое условие для правил короче четырёх
    return np.array(M), names, np.array(fam)


def combos(fam):
    nC = len(fam); byf = {}
    for i, f in enumerate(fam):
        byf.setdefault(f, []).append(i)
    fs = sorted(byf); out = []
    for k in (1, 2, 3, 4):
        for fsub in itertools.combinations(fs, k):
            for c in itertools.product(*[byf[f] for f in fsub]):
                out.append(c + (nC,) * (4 - k))
    return np.array(out, np.int16)


def wmat(T):
    w = (T // WEEK).astype(np.int64); u, inv = np.unique(w, return_inverse=True)
    W = np.zeros((len(T), len(u)), np.float32); W[np.arange(len(T)), inv] = 1
    return W


def evaluate(M, CB, y, T, chunk=8192):
    W = wmat(T); Wy = W * y[:, None].astype(np.float32)
    n = np.zeros(len(CB)); m = np.zeros(len(CB)); z = np.zeros(len(CB))
    for a in range(0, len(CB), chunk):
        c = CB[a:a + chunk]
        mf = (M[c[:, 0]] & M[c[:, 1]] & M[c[:, 2]] & M[c[:, 3]]).astype(np.float32)
        n[a:a + chunk], m[a:a + chunk], z[a:a + chunk] = zclust(mf @ W, mf @ Wy, axis=1)
    return n, m, z


def ct(x, t):
    x = np.asarray(x, float); w = (np.asarray(t, float) // WEEK).astype(np.int64); ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return (x.mean() if len(x) else np.nan), np.nan, len(x)
    mm = x.mean(); s = pd.Series(x - mm).groupby(w).sum(); se = np.sqrt((s ** 2).sum()) / len(x)
    return mm, (mm / se if se > 0 else np.nan), len(x)


def honest(sel, X, end):
    busy, take = {}, []
    for i in np.flatnonzero(sel & np.isfinite(end)):
        s = X.s.iat[i]; T = X["T"].iat[i]
        if T >= busy.get(s, -1):
            take.append(i); busy[s] = end[i]
    return np.array(take, int)


def placebo(X, tk, col):
    import fastbt as FB  # noqa: E402
    sl, hold = PAR[col]; out = np.full(len(tk), np.nan)
    for j, i in enumerate(tk):
        s = X.s.iat[i]
        if s not in FB.K:
            continue
        t = FB.K[s]["t"].astype(np.int64); v = []
        for d in (45, 90, 135):
            st = X["T"].iat[i] - d * DAY - 900; I = int(np.searchsorted(t, st))
            if 96 <= I < len(t) and t[I] == st:
                okt, net, *_ = FB.trades(s, np.array([I]), sl, hold, -1)
                if okt[0]:
                    v.append(net[0])
        out[j] = np.mean(v) if v else np.nan
    return out


def select(M, CB, y, T, seg):
    A, B = seg == 0, seg == 1
    nA, mA, zA = evaluate(M[:, A], CB, y[A], T[A])
    ok = (nA >= MINA) & (mA > 0)
    top = np.flatnonzero(ok)[np.argsort(-zA[ok])[:TOPA]]
    res = pd.DataFrame({"i": top, "n_A": nA[top], "m_A": mA[top], "z_A": zA[top]})
    for S, lab in ((1, "B"), (2, "C")):
        n, m, z = evaluate(M[:, seg == S], CB[top], y[seg == S], T[seg == S])
        res[f"n_{lab}"], res[f"m_{lab}"], res[f"z_{lab}"] = n, m, z
    res["passB"] = (res.n_B >= MINB) & (res.m_B > 0) & (res.z_B >= ZB)
    res["score"] = np.minimum(res.z_A, res.z_B)
    return res


def rule_name(c, names):
    return " & ".join(names[i] for i in c if i < len(names))


def main(cols, shuf):
    X = pd.read_pickle("s226_ev.pkl").sort_values(["T", "s"]).reset_index(drop=True)
    M0, names, fam = masks(X)
    CB = combos(fam)
    print(f"условий {len(names)} в {len(GROUPS)} группах, сочетаний {len(CB)}", flush=True)
    months = (T_END - T_BEG) / (30.44 * DAY)
    for col in cols:
        t0 = time.time()
        okr = X[col].notna().to_numpy()
        Xc = X[okr].reset_index(drop=True); M = M0[:, okr]
        T = Xc["T"].to_numpy(np.int64); seg = np.where(T < TA, 0, np.where(T < TB, 1, 2))
        y = Xc[col].to_numpy(float)
        runs = [("настоящие доходы", y)]
        if shuf:
            mon = pd.to_datetime(Xc["T"], unit="s").dt.to_period("M").astype(str).to_numpy()
            for sd in (0, 1, 2):
                rng = np.random.default_rng(sd); z = y.copy()
                for mm in np.unique(mon):
                    ix = np.flatnonzero(mon == mm); z[ix] = z[rng.permutation(ix)]
                runs.append((f"контроль {sd}", z))
        for lab, yy in runs:
            R = select(M, CB, yy, T, seg)
            P = R[R.passB].sort_values("score", ascending=False)
            base = [float(np.mean(yy[seg == S])) for S in (0, 1, 2)]
            print(f"\n=== шорт {col} — {lab}: событий A/B/C {[(seg == S).sum() for S in (0, 1, 2)]}, средние "
                  f"{base[0]:+.2%} / {base[1]:+.2%} / {base[2]:+.2%}; прошли A {len(R)}, прошли B {len(P)}; {time.time() - t0:.0f} с",
                  flush=True)
            if not len(P):
                continue
            # на C — настоящие доходы (для контроля правила выбраны по перемешанным)
            n, m, z = evaluate(M[:, seg == 2], CB[P.i.to_numpy()], y[seg == 2], T[seg == 2])
            P = P.assign(n_C=n, m_C=m, z_C=z)
            print(f"  прошедшие B на C: среднее {P.m_C.mean():+.2%}, в плюсе {(P.m_C > 0).mean():.0%}")
            show = P.head(10) if lab == "настоящие доходы" else P.head(1)
            for r in show.itertuples():
                print(f"  {rule_name(CB[r.i], names)} | A {r.m_A:+.2%} (n {r.n_A:.0f}, t {r.z_A:+.1f}) | "
                      f"B {r.m_B:+.2%} (n {r.n_B:.0f}, t {r.z_B:+.1f}) | C {r.m_C:+.2%} (n {r.n_C:.0f}, t {r.z_C:+.1f})")
            if lab != "настоящие доходы":
                continue
            best = CB[P.i.iat[0]]
            sel = M[best[0]] & M[best[1]] & M[best[2]] & M[best[3]]
            end = Xc["u_x_" + col].to_numpy(float)
            tk = honest(sel, Xc, end)
            mm, tt, nn = ct(y[tk], T[tk])
            h1, h2 = y[tk][T[tk] < MID].mean(), y[tk][T[tk] >= MID].mean()
            pl = placebo(Xc, tk, col); md, td, _ = ct(y[tk] - pl, T[tk])
            c = tk[seg[tk] == 2]; mc, tc, nc = ct(y[c], T[c])
            hz = Xc[HED[col]].to_numpy(float); mh, th, _ = ct(hz[tk], T[tk])
            print(f"  ВЫБРАНО: {rule_name(best, names)}")
            print(f"    честно весь период: {nn} сделок ({nn / months:.1f} в мес.), {mm:+.2%} (t {tt:+.1f}); половины "
                  f"{h1:+.2%} / {h2:+.2%}; сверх плацебо {md:+.2%} (t {td:+.1f}); с хеджем {mh:+.2%} (t {th:+.1f})")
            print(f"    честно на C: {nc} сделок, {mc:+.2%} (t {tc:+.1f})")
            ok = [("≥ 20 в мес.", nn / months >= 20), ("t ≥ 3", mm > 0 and tt >= 3), ("половины > 0", h1 > 0 and h2 > 0),
                  ("лучше плацебо", md > 0), ("C: > 0 и t ≥ 2", mc > 0 and tc >= 2)]
            print("    порог: " + "; ".join(f"{a} — {'да' if v else 'нет'}" for a, v in ok)
                  + ("  → ПРОЙДЕН" if all(v for _, v in ok) else "  → не пройден"), flush=True)
            P.assign(rule=[rule_name(CB[i], names) for i in P.i]).to_pickle(f"s226_top_{col}.pkl")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x != "shuffle"]
    main(a or list(PAR), "shuffle" in sys.argv[1:])
