"""s141 — непрерывные потоки предложения (гипотеза — ВЫВОДЫ.md, записана до расчёта). Потоки — s141_flows.pkl (прирост
за 7 сут вперёд по группам получателей к монетам в обращении по расписанию DefiLlama), сопоставление с перпами —
s139/map.pkl, разовые разлоки инсайдерам ≥ 1% (🔑) — s139/unlock_test.events(). Входы — понедельник 00:00 UTC, шорт 7 сут,
стоп +50% (s15/common.trade); хедж — индекс альтов s103 (равный вес, оборот ≥ 5 млн $ за сутки) на фактический срок сделки.
Запуск в папке периода: MC_K=… MC_F=… MC_CUT=… python3 <repo>/research/s141/flow_test.py <период>;
сводка из /home/user/mc_data: python3 … report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s139"):
    sys.path.insert(0, os.path.join(HERE, "..", p))

DAY = 86400
OUT = "/home/user/mc_data"
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01"), "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-11", "2025-12-01")}
THR = 0.005


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def alt_index(K):
    """Индекс альтов как s103/beta.index: равный вес, фьючерсы с оборотом ≥ 5 млн $ за прошлые сутки, без BTC."""
    syms = [s for s in K if s != "BTC" and len(K[s]["t"]) == len(K["BTC"]["t"])]
    C = np.vstack([K[s]["c"].astype(np.float32) for s in syms]); Q = np.vstack([K[s]["qv"].astype(np.float32) for s in syms])
    R = np.full(C.shape, np.nan, np.float32); R[:, 1:] = C[:, 1:] / C[:, :-1] - 1
    cs = np.cumsum(np.nan_to_num(Q, nan=0.0), axis=1, dtype=np.float64)
    v24 = np.zeros_like(cs); v24[:, 96:] = cs[:, 96:] - cs[:, :-96]
    ok = np.zeros(C.shape, bool); ok[:, 1:] = (v24[:, :-1] >= 5e6) & (Q[:, 1:] > 0)
    R = np.where(ok, np.clip(R, -0.5, 0.5), np.nan)
    with np.errstate(all="ignore"):
        m = np.nan_to_num(np.nanmean(R, axis=0), nan=0.0)
    return K["BTC"]["t"].astype(np.int64), np.cumprod(1 + m.astype(np.float64))


def run(per):
    from common import K, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    import unlock_test as U  # noqa: E402
    t0, t1, _ = PER[per]
    T, I = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T, a - 900, "right")) - 1; j = int(np.searchsorted(T, b - 900, "right")) - 1
        return I[j] / I[i] - 1 if 0 <= i <= j < len(I) else np.nan

    F = pd.read_pickle(f"{OUT}/s141_flows.pkl").set_index(["slug", "d"])
    M = pd.read_pickle(f"{OUT}/s139/map.pkl").set_index("slug")
    E = U.events(); E = E[(E.grp == "инсайдеры") & (E.share >= 0.01)]
    cl = {}
    for r in E.itertuples():
        cl.setdefault(r.slug, []).append(int(r.T))
    mondays = pd.date_range(t0, t1, freq="W-MON", tz="UTC")
    rows = []
    for mon in mondays:
        tm = int(mon.timestamp()); d = tm // DAY
        for slug in F.index.get_level_values(0).unique():
            key = M.at[slug, "fut"] if slug in M.index else None
            if not isinstance(key, str) or key not in K or (slug, d) not in F.index:
                continue
            lo, hi = live(key)
            if lo + 8 * DAY > tm or tm + 8 * DAY > hi:
                continue
            f = F.loc[(slug, d)]
            ins, inc, com, oth = (float(f.get(g, 0) or 0) for g in ("инсайдеры", "стимулы", "сообщество", "прочее"))
            u2 = any(tm <= x < tm + 8 * DAY for x in cl.get(slug, []))
            g1, g2 = ins >= THR and not u2, inc >= THR
            g0 = ins == 0 and inc == 0 and com == 0 and oth == 0
            if not (g1 or g2 or g0):
                continue
            i = idx_at(key, tm)
            x = trade(key, i, tp=None, sl=0.5, hold_h=168, side=-1) if i is not None else None
            if not x:
                continue
            t_end = int(K[key]["t"][i]) + 900 + int(x["bars"]) * 900
            rows.append(dict(s=key, slug=slug, t=tm, S1=g1, S2=g2, C=g0, ins=ins, inc=inc, net=x["net"],
                             hed=x["net"] + mv(tm, t_end), why=x["why"]))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s141_{per}.pkl")
    print(per, "недель", len(mondays), "сделок", len(X), "S1", int(X.S1.sum()), "S2", int(X.S2.sum()), "контроль", int(X.C.sum()))


def wk(x, col):
    """Среднее и t по средним за неделю входа."""
    w = x.groupby("t")[col].mean().dropna()
    return w.mean(), (w.mean() / (w.std(ddof=1) / np.sqrt(len(w))) if len(w) > 2 and w.std(ddof=1) > 0 else np.nan), len(x)


def diff(a, b, col):
    """S − контроль по неделям, где есть оба."""
    w = (a.groupby("t")[col].mean() - b.groupby("t")[col].mean()).dropna()
    return w.mean(), w.mean() / (w.std(ddof=1) / np.sqrt(len(w))) if len(w) > 2 else np.nan


def report():
    A = []
    for per, (t0, t1, cut) in PER.items():
        X = pd.read_pickle(f"{OUT}/s141_{per}.pkl"); X["per"] = per; A.append(X)
        months = (ts(t1) - ts(t0)) / (30.4 * DAY); c = ts(cut)
        print(f"\n{per}:")
        for lab, g in (("S1 вестинг инсайдеров", "S1"), ("S2 стимулы", "S2"), ("контроль (без прихода)", "C")):
            x = X[X[g]]
            if len(x) < 8:
                print(f"  {lab:24s} n={len(x)}"); continue
            m, t, n = wk(x, "net"); mh, th, _ = wk(x, "hed")
            print(f"  {lab:24s} n={n:5d} ({n / months:5.1f}/мес) шорт {m:+.2%} (t {t:+.1f}) | половины {x[x.t < c].net.mean():+.2%} / "
                  f"{x[x.t >= c].net.mean():+.2%} | с хеджем {mh:+.2%} (t {th:+.1f}) | стопов {(x.why == 'стоп').mean():.0%}")
        for g in ("S1", "S2"):
            d, t = diff(X[X[g]], X[X.C], "net"); dh, th = diff(X[X[g]], X[X.C], "hed")
            print(f"  {g} − контроль: шорт {d:+.2%} (t {t:+.1f}), с хеджем {dh:+.2%} (t {th:+.1f})")
    A = pd.concat(A, ignore_index=True)
    print("\nшесть лет:")
    for g in ("S1", "S2", "C"):
        x = A[A[g]]; m, t, n = wk(x, "net"); mh, th, _ = wk(x, "hed")
        print(f"  {g}: n={n} шорт {m:+.2%} (t {t:+.1f}), с хеджем {mh:+.2%} (t {th:+.1f})")
    for g in ("S1", "S2"):
        d, t = diff(A[A[g]], A[A.C], "hed"); print(f"  {g} − контроль с хеджем: {d:+.2%} (t {t:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
