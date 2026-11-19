"""s197 — «расписанный выход» (Г1 + Г2 s196): шорт перпа с закрытия часа ≥ max(t_vis + 15 мин, T − 7 сут) до T + 24 ч,
стоп +50%, не чаще одной сделки на монету за 7 сут по входу. Запись до расчёта — ВЫВОДЫ.md (коммит 35e42d4).

Запуск из /home/user/mc_data (свечи периода — MC_K / MC_F, как в s117):
  python3 run.py 2024–2026
  MC_K=s117/k_oos.pkl MC_F=s117/fund_oos.pkl python3 run.py 2022–2024
  MC_K=s117/k_2020.pkl MC_F=s117/fund_2020.pkl python3 run.py 2020–2022
  python3 run.py report
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
sys.path.insert(0, os.path.join(HERE, "..", "s182"))

DAY, OUT = 86400, "/home/user/mc_data"
EV = f"{OUT}/s197/events.pkl"
COV = f"{OUT}/s197/coverage.json"
G1 = {"atom", "tia", "kava", "dot", "ksm", "egld", "rose", "xtz", "apt"}
SL = 0.50
MAXN = 8 * 96                       # не дольше 8 сут (в 15-мин свечах)

# вариант → (отбор строк, выход: "T1" — T + 24 ч, "T0" — в T)
VARIANTS = {
    "main": (lambda E: (E.kind == "exit") & (E.f >= 0.001), "T1"),
    "big": (lambda E: (E.kind == "exit") & (E.f >= 0.005), "T1"),
    "mid": (lambda E: (E.kind == "exit") & (E.f >= 0.001) & (E.f < 0.005), "T1"),
    "turn": (lambda E: (E.kind == "exit") & (E.turn >= 0.25), "T1"),
    "g1": (lambda E: (E.kind == "exit") & (E.f >= 0.001) & E.src.isin(G1), "T1"),
    "g2": (lambda E: (E.kind == "exit") & (E.f >= 0.001) & ~E.src.isin(G1), "T1"),
    "norelock": (lambda E: (E.kind == "exit") & (E.f >= 0.001) & ~E.relocker.fillna(False).astype(bool), "T1"),
    "nounlock": (lambda E: (E.kind == "exit") & (E.f >= 0.001) & ~E.unlock3, "T1"),
    "exact": (lambda E: (E.kind == "exit") & (E.f >= 0.001) & E.T_exact.astype(bool), "T1"),
    "atT": (lambda E: (E.kind == "exit") & (E.f >= 0.001), "T0"),
    "ctl": (lambda E: (E.kind == "ctl") & (E.f >= 0.001), "T1"),
}
NAMES = {
    "main": "основной: Г1 ∪ Г2, ≥ 0,1%",
    "big": "≥ 0,5% обращения",
    "mid": "0,1…0,5% обращения",
    "turn": "≥ 0,25 суточного оборота перпа",
    "g1": "Г1 — PoS",
    "g2": "Г2 — DeFi",
    "norelock": "без ve-«перекладчиков»",
    "nounlock": "без разлока 🔑⁺ в ±3 сут от T",
    "exact": "только точный T",
    "atT": "выход в T",
    "ctl": "контроль: вход в блокировку → шорт 8 сут",
}


def unlocks(per):
    """Разлоки 🔑⁺ (s142) по перпу: массив времён T."""
    try:
        u = pd.read_pickle(f"{OUT}/s142_{per}.pkl")[["s", "T"]]
    except FileNotFoundError:
        return {}
    out = {}
    for s, T in zip(u.s, u["T"]):
        out.setdefault(s, []).append(int(T))
    return {k: np.sort(np.array(v)) for k, v in out.items()}


def load(per):
    import common182 as C  # noqa: E402
    E = pd.read_pickle(EV).copy()
    for c in ("relocker", "turn", "T_exact"):
        if c not in E:
            E[c] = np.nan if c == "turn" else False
    E["t_vis"] = E.t_vis.astype(np.int64)
    E["T"] = np.where(E["T"].notna(), E["T"], E.t_vis + 7 * DAY).astype(np.int64)   # у контроля нет T: срок 8 сут
    E["entry"] = (np.ceil(np.maximum(E.t_vis + 900, E["T"] - 7 * DAY) / 3600) * 3600).astype(np.int64)
    E["perp"] = E.sym.astype(str) + "USDT"
    t0, t1 = C.ts(C.PER[per][0]), C.ts(C.PER[per][1])
    E = E[(E.entry >= t0) & (E.entry < t1)].copy()
    U = unlocks(per)

    def near(s, T):
        a = U.get(s)
        if a is None or not len(a):
            return False
        j = np.searchsorted(a, T)
        return any(abs(a[k] - T) <= 3 * DAY for k in (j - 1, j) if 0 <= k < len(a))
    E["unlock3"] = [near(s, T) for s, T in zip(E.perp, E["T"])]
    return E


def book(FB, s, g, endcol):
    """Сделки по монете s: строки g (вход по времени entry), не чаще одной за 7 сут по входу."""
    K = FB.K
    t = K[s]["t"].astype(np.int64)
    lo, _ = FB.live(s)
    g = g.sort_values("entry")
    st = g.entry.values - 900
    I = np.searchsorted(t, st)
    ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == st) & (I >= 96)
    ok &= t[np.minimum(I, len(t) - 1)] >= lo + 30 * DAY                    # перп старше 30 сут
    end = g["T"].values + (DAY if endcol == "T1" else 0)
    n = np.round((end - g.entry.values) / 900).astype(np.int64)
    ok &= n >= 4
    g, I, n = g[ok].copy(), I[ok], np.minimum(n[ok], MAXN)
    keep = np.zeros(len(g), bool)
    last = -10 ** 12
    for j, e in enumerate(g.entry.values):
        if e >= last + 7 * DAY:
            keep[j] = True
            last = e
    g, I, n = g[keep].copy(), I[keep], n[keep]
    if not len(g):
        return None
    net = np.full(len(g), np.nan); stp = np.zeros(len(g), bool); pl = np.full(len(g), np.nan)
    mv = np.full(len(g), np.nan)
    for nv in np.unique(n):
        j = np.where(n == nv)[0]
        okt, r, sp, bars, tend = FB.trades(s, I[j], SL, nv / 4, -1)
        p = FB.placebo(s, I[j], SL, nv / 4, -1)
        m = FB.alt_mv(t[I[j]] + 900, tend)
        net[j] = np.where(okt, r, np.nan)
        stp[j] = np.where(okt, sp, False)
        pl[j] = p
        mv[j] = m
    g["net"], g["stop"], g["pl"] = net, stp, pl
    g["hed"] = net + mv
    g["hold_h"] = n / 4
    g["t"] = g.entry
    return g


def run(per):
    import fastbt as FB  # noqa: E402
    E = load(per)
    rows = []
    for v, (sel, endcol) in VARIANTS.items():
        Z = E[sel(E)]
        for s, g in Z.groupby("perp"):
            if s not in FB.K:
                continue
            x = book(FB, s, g, endcol)
            if x is not None:
                x["var"] = v
                rows.append(x)
    X = pd.concat(rows, ignore_index=True)
    X["per"] = per
    X.to_pickle(f"{OUT}/s197_{per}.pkl")
    print(per, X[X.net.notna()].groupby("var").size().to_dict(), flush=True)


def cov_months(per):
    """Месяцы охвата источника внутри периода (по t_vis)."""
    import common182 as C  # noqa: E402
    cv = json.load(open(COV))
    a, b = C.ts(C.PER[per][0]), C.ts(C.PER[per][1])
    out = {}
    for src, iv in cv.items():
        tot = 0.0
        for lo, hi in iv:
            lo_, hi_ = max(lo, a), min(hi, b)
            if hi_ > lo_:
                tot += hi_ - lo_
        out[src] = tot / (30.4 * DAY)
    return out


def report(pers=None):
    import common182 as C  # noqa: E402
    pers = pers or list(C.PER)
    print("s197 — «расписанный выход»: шорт перпа max(t_vis + 15 мин, T − 7 сут) → T + 24 ч, стоп 50%, комиссия и фандинг\n")
    ph, pn, pd_, pc = [], [], [], []
    for per in pers:
        X = pd.read_pickle(f"{OUT}/s197_{per}.pkl")
        X = X[X.net.notna()].copy()
        X["why"] = np.where(X.stop, "стоп", "время")
        print(f"== {per} ==")
        for v in VARIANTS:
            print(f"  {NAMES[v]}: {C.line(X[X['var'] == v], per)}")
        x = X[X["var"] == "main"]
        cm = cov_months(per)
        freq = sum(len(x[x.src == s]) / cm[s] for s in x.src.unique() if cm.get(s, 0) > 0.5)
        print(f"  частота основного на месяц охвата: {freq:.1f} (просто в месяц {len(x) / C.months(per):.1f})")
        by = x.groupby("src").net.agg(["size", "mean"])
        print("  по источникам: " + "; ".join(f"{s} {int(r['size'])} {r['mean']:+.2%}" for s, r in by.iterrows()))
        m, t, n = C.ct(x.net, x.t)
        mh, th, _ = C.ct(x.hed, x.t)
        pn.append((m, abs(m / t) if t else np.nan, n))
        ph.append((mh, abs(mh / th) if th else np.nan, n))
        y = X[X["var"].isin(["big", "mid"])]
        d, se = C.diff(y.net, y["var"] == "big", y.t)
        pd_.append((d, se, len(y)))
        print(f"  Δ ≥ 0,5% − 0,1…0,5%: {d:+.2%} (t {d / se:+.1f})" if se else "  Δ ≥ 0,5% − 0,1…0,5%: мало сделок")
        y = X[X["var"].isin(["main", "ctl"])]
        d, se = C.diff(y.net, y["var"] == "main", y.t)
        pc.append((d, se, len(y)))
        print(f"  Δ выход − контроль: {d:+.2%} (t {d / se:+.1f})" if se else "  Δ выход − контроль: мало сделок")
        if per == "2024–2026":
            cut = C.ts(C.PER[per][2])
            h1, h2 = x[x.t < cut].net.mean(), x[x.t >= cut].net.mean()
            crit = [("≥ 20 в месяц охвата", freq >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                    ("сверх плацебо > 0", (x.net - x.pl).mean() > 0), ("с хеджем > 0", mh > 0)]
            print("  правило владельца: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in crit))
        print()
    if len(pers) == 3:
        m, t = C.combine(pn)
        mh, th = C.combine(ph)
        print(f"Три периода, основной: {m:+.2%} (t {t:+.1f}); с хеджем {mh:+.2%} (t {th:+.1f})")
        print("  по периодам: " + " / ".join(f"{a:+.2%}" for a, _, _ in pn) + "; с хеджем " +
              " / ".join(f"{a:+.2%}" for a, _, _ in ph))
        d, t = C.combine(pd_)
        print(f"Доза ≥ 0,5% − 0,1…0,5% вместе: {d:+.2%} (t {t:+.1f})")
        d, t = C.combine(pc)
        print(f"Выход − контроль вместе: {d:+.2%} (t {t:+.1f})")


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report(sys.argv[2:] or None)
    else:
        run(sys.argv[1])
