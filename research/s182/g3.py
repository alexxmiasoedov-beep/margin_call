"""s182 Г3 — недельная корзина «казна раздаёт токены» (гипотеза — ВЫВОДЫ.md, записана до расчёта).
Вселенная — перпы с адресами казначейств в сборе s181 (s181/treasury_out.pkl, без BNT/Bancor). Каждый понедельник 00:00 UTC
F = Σ выходов собственного токена из казны за прошлые 28 сут к обращению CMC (без перекладки между казнами, сжигания,
Bancor). Событие — F ≥ 0,5%, контроль — та же вселенная в тот же понедельник с F < 0,5%. Шорт с закрытия свечи
00:00–00:15 на 168 ч, стоп +25%; хедж — индекс альтов s103 на фактический срок; плацебо — та же монета за 45/90/135 сут.
Запуск из /home/user/mc_data: [MC_K=… MC_F=…] python3 <repo>/research/s182/g3.py <период>; сводка: … g3.py report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common182 as C  # noqa: E402

DAY, OUT = C.DAY, C.OUT
SALE = {"биржа", "кастоди/ММ", "DEX/агрегатор"}


def outflows():
    X = pd.read_pickle(f"{OUT}/s181/treasury_out.pkl")
    uni = sorted(set(X.perp) - {"BNT"})
    X = X[~X.protos.map(lambda s: "bancor" in s) & ~X.dst.isin(["та же казна/другая казна", "сжигание"])]
    X = X[X.frac.notna() & X.perp.isin(uni)]
    return X, uni


def run(per):
    from common import K, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    t0, t1, _ = C.PER[per]
    T, I = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T, a - 900, "right")) - 1; j = int(np.searchsorted(T, b - 900, "right")) - 1
        return I[j] / I[i] - 1 if 0 <= i <= j < len(I) else np.nan

    X, uni = outflows()
    G = {p: (g.t.to_numpy(float), g.frac.to_numpy(float), g.dst.isin(SALE).to_numpy()) for p, g in X.groupby("perp")}
    W = pd.date_range(t0, t1, freq="W-MON", tz="UTC")
    rows = []
    for w in W:
        w = int(w.timestamp())
        if w >= C.ts(t1):
            continue
        te = w + 900
        for p in uni:
            if p not in K:
                continue
            lo, hi = live(p)
            if not np.isfinite(lo) or te < lo + DAY:
                continue
            i = idx_at(p, te)
            if i is None or int(K[p]["t"][i]) != w:
                continue
            if p in G:
                tt, ff, ss = G[p]
                m = (tt >= w - 28 * DAY) & (tt < w)
                F = ff[m].sum(); Fs = ff[m & ss].sum()
                m0 = (tt >= w - 56 * DAY) & (tt < w - 28 * DAY)
                F0 = ff[m0].sum()
            else:
                F = Fs = F0 = 0.0
            x = trade(p, i, tp=None, sl=0.25, hold_h=168, side=-1)
            if not x:
                continue
            t_end = int(K[p]["t"][i]) + 900 + int(x["bars"]) * 900
            pl = []
            for dd in (45, 90, 135):
                j = idx_at(p, te - dd * DAY)
                y = trade(p, j, tp=None, sl=0.25, hold_h=168, side=-1) if j is not None else None
                if y:
                    pl.append(y["net"])
            rows.append(dict(s=p, t=te, F=F, Fs=Fs, F0=F0, net=x["net"], why=x["why"], hed=x["net"] + mv(te, t_end),
                             pl=np.mean(pl) if pl else np.nan))
    R = pd.DataFrame(rows)
    R.to_pickle(f"{OUT}/s182_g3_{per}.pkl")
    print(per, "сделок", len(R), "событий F ≥ 0,5%", int((R.F >= 0.005).sum()), flush=True)


def report():
    parts, parts_h, A = [], [], []
    print("Г3 — недельная корзина: F ≥ 0,5% за 28 сут против прочих монет вселенной; шорт 7 сут, стоп 25%\n")
    for per in C.PER:
        R = pd.read_pickle(f"{OUT}/s182_g3_{per}.pkl"); R["per"] = per; A.append(R)
        ev = R.F >= 0.005
        d, se = C.diff(R.net, ev, R.t); dh, seh = C.diff(R.hed, ev, R.t)
        parts.append((d, se, int(ev.sum()))); parts_h.append((dh, seh, int(ev.sum())))
        print(f"{per}: монет во вселенной (медиана по неделям) {R.groupby('t').size().median():.0f}")
        print(f"  события  {C.line(R[ev], per)}")
        print(f"  контроль {C.line(R[~ev], per)}")
        print(f"  Δ = {d:+.2%} (t {d / se:+.1f}); с хеджем Δ = {dh:+.2%} (t {dh / seh:+.1f})")
    m, t = C.combine(parts); mh, th = C.combine(parts_h)
    print(f"\nвместе: Δ = {m:+.2%} (t {t:+.1f}); с хеджем Δ = {mh:+.2%} (t {th:+.1f})")
    A = pd.concat(A, ignore_index=True)
    top = A[A.F >= 0.005].groupby("s").size().sort_values(ascending=False)
    print("монеты с наибольшим числом событий:", top.head(8).to_dict())
    A["rk"] = A.groupby("t").F.rank(ascending=False, method="first")
    print("\nРазрезы (Δ к контролю F < 0,5%, по периодам):")
    ev = A.F >= 0.005
    sl = {"потолок 5 монет": ev & (A.rk <= 5), "F 0,5–1%": ev & (A.F < 0.01), "F 1–3%": (A.F >= 0.01) & (A.F < 0.03),
          "F ≥ 3%": A.F >= 0.03, "продажа видна (≥ 0,05%)": ev & (A.Fs >= 0.0005),
          "продажа не видна": ev & (A.Fs < 0.0005), "новое (прошлое окно < 0,5%)": ev & (A.F0 < 0.005),
          "серия": ev & (A.F0 >= 0.005), "без трёх монет с наибольшим числом": ev & ~A.s.isin(top.index[:3])}
    for lab, msk in sl.items():
        out = []
        for per in C.PER:
            x = A[A.per == per]; s = msk[A.per == per]; c = x.F < 0.005
            z = x[s | c]
            d, se = C.diff(z.net, s[z.index], z.t)
            out.append(f"n={int(s.sum()):3d} {x[s].net.mean():+.2%} Δ {d:+.2%} (t {d / se:+.1f})" if s.sum() >= 5 else
                       f"n={int(s.sum()):3d}")
        print(f"  {lab:38s} " + " | ".join(out))
    out = []
    for per in C.PER:
        x = A[A.per == per]; e = x.F >= 0.005; c0 = x.F < 0.0005
        z = x[e | c0]
        d, se = C.diff(z.net, e[z.index], z.t)
        out.append(f"контроль n={int(c0.sum()):4d} Δ {d:+.2%} (t {d / se:+.1f})")
    print(f"  {'контроль «без выходов» (F < 0,05%)':38s} " + " | ".join(out))


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
