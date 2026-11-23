"""s259, вопрос 1 — премия перпа к индексу (premiumIndexKlines, s12/prem.pkl: 15 мин, закрытие): величина, частота отрывов,
длительность эпизодов, скорость схождения; перпы без спота против монет со спотом (все и при равном обороте), самоссылка
индекса (снимок s252, только 07–10.2026), монеты до и после листинга спота. Доходы не считаются.
Премия p — индекс премии Binance по ценам удара (impact bid/ask), из него считается фандинг; внутри спреда удара p = 0.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s259/study/premium.py"""
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common259 import BAR, DAY, MID, OUT, T0, T1, load_k  # noqa: E402

TH = (0.005, 0.01, 0.02, 0.05)
EXIT = 0.001
SNAP0 = int(pd.Timestamp("2026-07-01", tz="UTC").timestamp())


def panel():
    """Список перпов с массивами: t, c, p, qv, оборот 7 сут ($/сут), без спота (bool) — только живые свечи в [T0, T1)."""
    K = load_k()
    PR = pickle.load(open("s12/prem.pkl", "rb"))
    U = json.load(open(f"{OUT}/universe.json"))
    out = {}
    for s, u in U.items():
        if s not in PR:
            continue
        a = K[s]; t = a["t"]
        pt, pv = PR[s]
        ip = np.searchsorted(pt, t); ip2 = np.minimum(ip, len(pt) - 1)
        okp = (ip < len(pt)) & (pt[ip2] == t)
        qv = a["qv"].astype(float)
        cs = np.r_[0.0, np.cumsum(qv)]
        n = np.arange(len(t))
        lo = np.maximum(n - 671, 0)
        to7 = (cs[n + 1] - cs[lo]) / np.maximum(n + 1 - lo, 1) * 96         # средний оборот за сутки по 7 сут
        keep = okp & (qv > 0) & (t + BAR >= T0) & (t + BAR < T1) & (n >= 96)
        if keep.sum() < 96:
            continue
        s0 = u["spot0"] or np.inf
        out[s] = dict(t=t[keep], c=a["c"][keep].astype(float), p=pv[ip2[keep]].astype(float), to7=to7[keep],
                      ns=(t[keep] + BAR) < s0, spot0=u["spot0"], snap=u["snap"], self=u.get("self", np.nan),
                      alpha=u.get("alpha", np.nan), ext_max=u.get("ext_max", np.nan))
    return out


def episodes(t, p, th, sign):
    """Эпизоды: вход p·sign ≥ th, выход p·sign < EXIT; разрыв в данных — конец (цензура). [(старт, конец|None, пик)]"""
    x = p * sign
    ev = np.where(x >= th, 1.0, np.where(x < EXIT, 0.0, np.nan))
    gap = np.r_[False, np.diff(t) != BAR]
    ev[gap & np.isnan(ev)] = 0.0                                              # после разрыва — заново
    st = pd.Series(ev).ffill().fillna(0).values.astype(int)
    d = np.diff(np.r_[0, st, 0])
    starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    res = []
    for a, b in zip(starts, ends):
        cens = b >= len(t) or (b < len(t) and gap[b] and x[b] >= EXIT)
        g = np.flatnonzero(gap[a + 1:b])
        if len(g):                                                           # разрыв внутри — цензура
            b = a + 1 + g[0]; cens = True
        res.append((a, None if cens else b, float(x[a:b].max())))
    return res


def q(x, qs=(.01, .05, .25, .5, .75, .95, .99)):
    x = np.asarray(x, float)
    return " ".join(f"{v:+.2%}" for v in np.quantile(x, qs)) if len(x) else "—"


def describe(P, sel, name):
    """Распределение и эпизоды по группе свечей: sel(s, d) → маска свечей перпа s."""
    ps, n_bars, eps, perps = [], 0, {th: [] for th in TH}, set()
    days = 0.0
    for s, d in P.items():
        m = sel(s, d)
        if not m.any():
            continue
        perps.add(s)
        ps.append(d["p"][m]); n_bars += m.sum(); days += m.sum() / 96
        idx = np.flatnonzero(m)
        t, p = d["t"][idx], d["p"][idx]
        for th in TH:
            for sign in (1, -1):
                for a, b, pk in episodes(t, p, th, sign):
                    eps[th].append((s, int(t[a]), sign, None if b is None else (b - a) * 0.25, pk))
    p = np.concatenate(ps) if ps else np.zeros(0)
    print(f"\n== {name}: перпов {len(perps)}, монето-суток {days:,.0f}")
    print(f"  p квантили 1/5/25/50/75/95/99%: {q(p)}; доля p = 0: {(p == 0).mean():.0%}; среднее {p.mean():+.3%}")
    print("  доля свечей |p| ≥ 0,1/0,3/0,5/1/2/5%: " + " / ".join(f"{(np.abs(p) >= x).mean():.2%}" for x in (0.001, 0.003, 0.005, 0.01, 0.02, 0.05))
          + f"; p ≥ +0,5%: {(p >= 0.005).mean():.2%}, p ≤ −0,5%: {(p <= -0.005).mean():.2%}")
    res = {"perps": len(perps), "days": days}
    for th in TH:
        E = pd.DataFrame(eps[th], columns=["s", "t", "sign", "dur_h", "peak"])
        if not len(E):
            continue
        mo = days / 30.44
        dur = E.dur_h.dropna()
        pos, neg = E[E.sign > 0], E[E.sign < 0]
        print(f"  эпизоды |p| ≥ {th:.1%} (до |p| < 0,1%): {len(E)} — {len(E) / days * 100:.1f} на 100 монето-суток "
              f"(+ {len(pos)}, − {len(neg)}); длительность ч: медиана {dur.median():.2f}, 75% {dur.quantile(.75):.2f}, "
              f"90% {dur.quantile(.9):.2f}, > 8 ч {(dur > 8).mean():.0%}; цензура {E.dur_h.isna().mean():.0%}; "
              f"пик медиана {E.peak.median():.2%}; знак +: медиана {pos.dur_h.median():.2f} ч, −: {neg.dur_h.median():.2f} ч")
        res[th] = E
    return res


def decay(P, sel, name, th=0.01):
    """Схождение после входа в эпизод |p| ≥ th: медиана |p(t+k)| / |p(старт)|, время до половины."""
    rat = {k: [] for k in (1, 2, 4, 8, 16, 32, 96)}
    half = []
    for s, d in P.items():
        m = sel(s, d)
        if not m.any():
            continue
        idx = np.flatnonzero(m); t, p = d["t"][idx], d["p"][idx]
        for sign in (1, -1):
            x = p * sign
            for a, b, pk in episodes(t, p, th, sign):
                x0 = x[a]
                for k in rat:
                    if a + k < len(x) and t[a + k] == t[a] + k * BAR:
                        rat[k].append(x[a + k] / x0)
                h = np.flatnonzero(x[a:a + 97] < x0 / 2)
                cont = a + 96 < len(t) and t[a + 96] == t[a] + 96 * BAR
                half.append(h[0] * 0.25 if len(h) else (np.inf if cont else np.nan))
    hf = pd.Series(half).dropna()
    print(f"  {name}: схождение после |p| ≥ {th:.0%} — медиана p(t+k)/p(0) при k = 15 мин/30 мин/1 ч/2 ч/4 ч/8 ч/24 ч: "
          + " / ".join(f"{np.median(v):.2f}" for v in rat.values()) + f"; до половины: медиана {hf.median():.2f} ч, "
          f"за 15 мин {(hf <= 0.25).mean():.0%}, за 1 ч {(hf <= 1).mean():.0%}, дольше суток {np.isinf(hf).mean():.0%}")


def main():
    P = panel()
    print(f"перпов в панели: {len(P)}")
    allb = np.concatenate([d["to7"] for d in P.values()])
    edges = np.quantile(allb[allb > 0], np.linspace(0, 1, 6)[1:-1])
    print("границы пятых долей оборота за сутки (7 сут), $: " + " / ".join(f"{e / 1e6:.1f} млн" for e in edges))
    for d in P.values():
        d["bk"] = np.searchsorted(edges, d["to7"])
    nos = lambda s, d: d["ns"]  # noqa: E731
    spt = lambda s, d: ~d["ns"]  # noqa: E731
    R = {}
    R["ns"] = describe(P, nos, "без спота")
    R["sp"] = describe(P, spt, "со спотом")
    for h, (lo, hi) in (("1-я половина", (T0, MID)), ("2-я половина", (MID, T1))):
        describe(P, lambda s, d, lo=lo, hi=hi: d["ns"] & (d["t"] >= lo) & (d["t"] < hi), f"без спота, {h}")
        describe(P, lambda s, d, lo=lo, hi=hi: ~d["ns"] & (d["t"] >= lo) & (d["t"] < hi), f"со спотом, {h}")
    print("\n### по пятым долям оборота (1 — меньший)")
    for b in range(5):
        describe(P, lambda s, d, b=b: d["ns"] & (d["bk"] == b), f"без спота, оборот {b + 1}")
        describe(P, lambda s, d, b=b: ~d["ns"] & (d["bk"] == b), f"со спотом, оборот {b + 1}")
    print("\n### схождение")
    decay(P, nos, "без спота"); decay(P, spt, "со спотом")
    decay(P, nos, "без спота", 0.02); decay(P, spt, "со спотом", 0.02)
    for b in range(5):
        decay(P, lambda s, d, b=b: d["ns"] & (d["bk"] == b), f"без спота, оборот {b + 1}")
        decay(P, lambda s, d, b=b: ~d["ns"] & (d["bk"] == b), f"со спотом, оборот {b + 1}")
    print("\n### самоссылка индекса (перпы снимка 23.11.2026 без спота, свечи 07–10.2026)")
    late = lambda d: d["ns"] & (d["t"] >= SNAP0) & d["snap"]  # noqa: E731
    describe(P, lambda s, d: late(d) & (d["self"] > 0), "сам перп в индексе")
    describe(P, lambda s, d: late(d) & (d["self"] == 0), "перпа в индексе нет")
    describe(P, lambda s, d: late(d) & (d["self"] >= 0.25), "вес перпа ≥ 0,25")
    describe(P, lambda s, d: late(d) & (d["alpha"] > 0), "Alpha в индексе")
    describe(P, lambda s, d: late(d) & (d["alpha"] == 0), "Alpha в индексе нет")
    decay(P, lambda s, d: late(d) & (d["self"] > 0), "сам перп в индексе")
    decay(P, lambda s, d: late(d) & (d["self"] == 0), "перпа в индексе нет")
    for b in range(5):
        describe(P, lambda s, d, b=b: late(d) & (d["self"] > 0) & (d["bk"] == b), f"самоссылка, оборот {b + 1}")
        describe(P, lambda s, d, b=b: late(d) & (d["self"] == 0) & (d["bk"] == b), f"без самоссылки, оборот {b + 1}")
    print("\n### до и после листинга спота (перпы с переходом, ±30 сут, без 3 сут вокруг)")
    tr = {s for s, d in P.items() if d["spot0"] and d["t"][0] + 30 * DAY < d["spot0"] < d["t"][-1] - 30 * DAY}
    print("перпов с переходом и 30 сут по обе стороны:", len(tr))
    bef = lambda s, d: (s in tr) & (d["t"] >= (d["spot0"] or 0) - 30 * DAY) & (d["t"] < (d["spot0"] or 0) - 3 * DAY)  # noqa: E731
    aft = lambda s, d: (s in tr) & (d["t"] >= (d["spot0"] or 0) + 3 * DAY) & (d["t"] < (d["spot0"] or 0) + 30 * DAY)  # noqa: E731
    describe(P, bef, "за 30…3 сут до спота"); describe(P, aft, "через 3…30 сут после спота")
    decay(P, bef, "до спота"); decay(P, aft, "после спота")
    rows = []
    for s in tr:
        d = P[s]
        a = np.abs(d["p"][bef(s, d)]); b = np.abs(d["p"][aft(s, d)])
        if len(a) > 500 and len(b) > 500:
            rows.append((s, (a >= 0.005).mean(), (b >= 0.005).mean(), np.median(d["to7"][bef(s, d)]), np.median(d["to7"][aft(s, d)])))
    X = pd.DataFrame(rows, columns=["s", "b5", "a5", "tob", "toa"])
    print(f"попарно по монетам ({len(X)}): доля |p| ≥ 0,5% до {X.b5.median():.2%} → после {X.a5.median():.2%} (медианы), "
          f"снизилась у {(X.a5 < X.b5).mean():.0%}; оборот перпа до {X.tob.median() / 1e6:.1f} → после {X.toa.median() / 1e6:.1f} млн $/сут")
    pickle.dump({k: {th: v[th] for th in TH if th in v} for k, v in R.items()}, open(f"{OUT}/prem_episodes.pkl", "wb"))


if __name__ == "__main__":
    main()
