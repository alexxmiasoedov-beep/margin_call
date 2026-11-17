"""s139 — разлоки DefiLlama по получателям (гипотеза — ВЫВОДЫ.md, записана до расчёта). Данные — s139/ll/e_<slug>.json
(ll_fetch.py), сопоставление с перпами — s139/map.pkl. U1: разовый разлок инсайдерам (insiders, privateSale) ≥ 5% монет
в обращении по расписанию → шорт за 7 сут до T, выход через сутки после (192 ч), стоп +50%. U2: инсайдерам ≥ 1%.
U3: сообществу ≥ 5%. U4: как U1, но шорт за 30 сут до T, выход за 7 сут. Плацебо — та же монета за 45/90/135 сут.
Запуск в папке периода: MC_K=… MC_F=… MC_CUT=… python3 <repo>/research/s139/unlock_test.py <период>;
сводка из /home/user/mc_data: python3 … report"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))

DAY = 86400
OUT = "/home/user/mc_data"
LL = f"{OUT}/s139/ll"
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01"), "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-19", "2025-12-01")}
INS = {"insiders", "privateSale"}
NOT_COMM = {"noncirculating", "burned"}


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def events():
    """Разовые разлоки: проект, сутки, группа получателей, токенов, доля к монетам в обращении по расписанию."""
    M = pd.read_pickle(f"{OUT}/s139/map.pkl").set_index("slug")
    rows = []
    for f in sorted(glob.glob(f"{LL}/e_*.json")):
        slug = os.path.basename(f)[2:-5]
        if slug not in M.index or not isinstance(M.at[slug, "fut"], str):
            continue
        try:
            E = json.load(open(f))
        except Exception:
            continue
        cats = E.get("categories") or {}
        nonc = set(cats.get("noncirculating", []))
        ser = []
        for sec in (E.get("documentedData") or {}).get("data") or []:
            if sec.get("label") in nonc or not sec.get("data"):
                continue
            d = pd.DataFrame(sec["data"])
            if "timestamp" not in d or "unlocked" not in d:
                continue
            ser.append(pd.Series(d.unlocked.astype(float).values, index=d.timestamp.astype(float).astype(np.int64)))
        if not ser:
            continue
        circ = pd.concat(ser, axis=1).sort_index().ffill().fillna(0).sum(axis=1)
        agg = {}
        for ev in (E.get("metadata") or {}).get("events") or []:
            if ev.get("unlockType") != "cliff":
                continue
            try:
                t = int(float(ev["timestamp"])); n = float(sum(ev.get("noOfTokens") or [0]))
            except Exception:
                continue
            c = ev.get("category")
            g = "инсайдеры" if c in INS else (None if c in NOT_COMM else "сообщество")
            if g is None or n <= 0:
                continue
            k = (t // DAY, g)
            agg[k] = (min(agg.get(k, (t, 0))[0], t), agg.get(k, (t, 0))[1] + n)
        for (_, g), (t, n) in agg.items():
            before = circ[circ.index <= t - DAY]
            c0 = float(before.iloc[-1]) if len(before) else 0.0
            if c0 <= 0:
                continue
            rows.append(dict(slug=slug, key=M.at[slug, "fut"], T=t, grp=g, tokens=n, share=n / c0))
    return pd.DataFrame(rows).sort_values("T").reset_index(drop=True)


def run(per):
    from common import K, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    t0, t1, _ = PER[per]
    E = events()
    E = E[(E["T"] >= ts(t0)) & (E["T"] < ts(t1))]
    hyps = [("U1", "инсайдеры", 0.05, 7, 192), ("U2", "инсайдеры", 0.01, 7, 192), ("U3", "сообщество", 0.05, 7, 192),
            ("U4", "инсайдеры", 0.05, 30, 552)]
    rows, last = [], {}
    for r in E.itertuples():
        if r.key not in K:
            continue
        lo, hi = live(r.key)
        for h, g, thr, back, hold in hyps:
            if r.grp != g or r.share < thr:
                continue
            te = r.T - back * DAY
            if lo + DAY > te or te < last.get((h, r.key), -1):
                continue
            i = idx_at(r.key, te)
            x = trade(r.key, i, tp=None, sl=0.5, hold_h=hold, side=-1) if i is not None else None
            if not x:
                continue
            last[(h, r.key)] = te + 7 * DAY
            pl = []
            for dd in (45, 90, 135):
                j = idx_at(r.key, te - dd * DAY)
                y = trade(r.key, j, tp=None, sl=0.5, hold_h=hold, side=-1) if j is not None else None
                if y:
                    pl.append(y["net"])
            rows.append(dict(hyp=h, s=r.key, slug=r.slug, T=r.T, t=te, share=r.share, net=x["net"], why=x["why"],
                             pl=np.mean(pl) if pl else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s139_{per}.pkl")
    print(per, "событий", len(E), "сделок", X.groupby("hyp").size().to_dict() if len(X) else 0)


def diff(a, b):
    da = a.groupby(pd.to_datetime(a.t, unit="s").dt.date).net.mean()
    db = b.groupby(pd.to_datetime(b.t, unit="s").dt.date).net.mean()
    d = a.net.mean() - b.net.mean(); se = np.sqrt(da.var() / len(da) + db.var() / len(db))
    return d, d / se if se > 0 else np.nan


def report():
    from oi_test import ct  # noqa: E402
    A = []
    for per, (t0, t1, cut) in PER.items():
        X = pd.read_pickle(f"{OUT}/s139_{per}.pkl"); X["per"] = per
        A.append(X)
        months = (ts(t1) - ts(t0)) / (30.4 * DAY)
        print(f"\n{per}:")
        for h in ("U1", "U2", "U3", "U4"):
            x = X[X.hyp == h]
            if len(x) < 8:
                print(f"  {h} n={len(x)}" + (f" {x.net.mean():+.2%}" if len(x) else "")); continue
            m, t, n = ct(x.net, x.t); dp = (x.net - x.pl).dropna()
            md, td, _ = ct(dp, x.t[(x.net - x.pl).notna()]) if len(dp) >= 8 else (np.nan, np.nan, 0)
            print(f"  {h} n={n:4d} ({n / months:4.1f}/мес) {m:+.2%} (t {t:+.1f}) в плюсе {(x.net > 0).mean():.0%} "
                  f"стопов {(x.why == 'стоп').mean():.0%} | половины {x[x.t < ts(cut)].net.mean():+.2%} / "
                  f"{x[x.t >= ts(cut)].net.mean():+.2%} | сверх плацебо {md:+.2%} (t {td:+.1f})")
    A = pd.concat(A, ignore_index=True)
    print("\nшесть лет:")
    for h in ("U1", "U2", "U3", "U4"):
        x = A[A.hyp == h]
        if len(x) < 8:
            print(f"  {h}: n={len(x)}"); continue
        m, t, n = ct(x.net, x.t); dp = (x.net - x.pl).dropna(); md, td, _ = ct(dp, x.t[(x.net - x.pl).notna()])
        print(f"  {h}: n={n} {m:+.2%} (t {t:+.1f}), сверх плацебо {md:+.2%} (t {td:+.1f})")
    d, t = diff(A[A.hyp == "U1"], A[A.hyp == "U3"])
    print(f"  U1 − U3: {d:+.2%} (t {t:+.1f})")
    A.to_pickle(f"{OUT}/s139_all.pkl")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
