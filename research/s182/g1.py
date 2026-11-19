"""s182 Г1 — двойник 🔑⁺ «разлок вместе с долей казны» (гипотеза — ВЫВОДЫ.md, записана до расчёта).
База — сделки 🔑⁺ бэктеста s142 (s142_<период>.pkl в папке данных: разовый разлок вне noncirculating ≥ 1% обращения,
шорт T − 7 → T + 1 сут, стоп +50%, хедж индексом альтов, плацебо 45/90/135 сут). N — сумма разовых разлоков категории
noncirculating того же проекта DefiLlama в сутки [T − 3; T + 3] к обращению по расписанию без noncirculating.
Событие — N ≥ 0,5%, контроль — N = 0. Запуск: python3 <repo>/research/s182/g1.py"""
import glob
import json
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "s139"))
sys.path.insert(0, os.path.join(HERE, "..", "s142"))
import common182 as C  # noqa: E402

DAY, OUT = C.DAY, C.OUT
LL = f"{OUT}/s139/ll"
LAB = (re.compile(r"from (.+?) on \{timestamp\}"), re.compile(r"of (.+?) tokens were unlocked"),
       re.compile(r"unlocked from (.+)$"))
FT = re.compile(r"foundation|treasury", re.I)


def nonc():
    """Разовые разлоки категории noncirculating: проект, время, доля к обращению по расписанию без noncirculating, метка."""
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
        nc = set((E.get("categories") or {}).get("noncirculating", []))
        ser = []
        for sec in (E.get("documentedData") or {}).get("data") or []:
            if sec.get("label") in nc or not sec.get("data"):
                continue
            d = pd.DataFrame(sec["data"])
            if "timestamp" not in d or "unlocked" not in d:
                continue
            ser.append(pd.Series(d.unlocked.astype(float).values, index=d.timestamp.astype(float).astype(np.int64)))
        if not ser:
            continue
        circ = pd.concat(ser, axis=1).sort_index().ffill().fillna(0).sum(axis=1)
        for ev in (E.get("metadata") or {}).get("events") or []:
            if ev.get("unlockType") != "cliff" or ev.get("category") != "noncirculating":
                continue
            try:
                t = int(float(ev["timestamp"])); n = float(sum(ev.get("noOfTokens") or [0]))
            except Exception:
                continue
            if n <= 0:
                continue
            before = circ[circ.index <= t - DAY]
            c0 = float(before.iloc[-1]) if len(before) else 0.0
            if c0 <= 0:
                continue
            desc = ev.get("description") or ""
            lab = next((m.group(1) for m in (p.search(desc) for p in LAB) if m), "")
            rows.append(dict(slug=slug, t=t, day=t // DAY, share=n / c0, lab=lab))
    return pd.DataFrame(rows)


def build():
    import any_test as A  # noqa: E402  (s142)
    N = nonc()
    Ev = A.events()                                     # все события 🔑⁺ (≥ 1%), для «ежемесячного графика»
    Ev["day"] = Ev["T"] // DAY
    nd = {s: g.day.to_numpy() for s, g in N.groupby("slug")}
    ev_days = {s: np.unique(g.day.to_numpy()) for s, g in Ev.groupby("slug")}
    out = []
    for per in C.PER:
        X = pd.read_pickle(f"{OUT}/s142_{per}.pkl"); X["per"] = per
        Nn, Nft, joint = [], [], []
        for r in X.itertuples():
            d = int(r.T // DAY)
            y = N[(N.slug == r.slug) & (N.day >= d - 3) & (N.day <= d + 3)] if r.slug in nd else N.iloc[:0]
            Nn.append(y.share.sum()); Nft.append(y[y.lab.str.contains(FT)].share.sum())
            # ежемесячный график: прошлые сутки-события 🔑⁺ проекта за 365 сут с разлоком казны в ±3 сут
            k = 0
            for e in ev_days.get(r.slug, []):
                if d - 365 <= e < d and r.slug in nd and np.any(np.abs(nd[r.slug] - e) <= 3):
                    k += 1
            joint.append(k)
        X["N"], X["Nft"], X["joint"] = Nn, Nft, joint
        out.append(X)
    X = pd.concat(out, ignore_index=True)
    X.to_pickle(f"{OUT}/s182_g1.pkl")
    return X


def report(X):
    X = X.copy()
    X["ev"] = X.N >= 0.005
    X["ctl"] = X.N == 0
    parts, parts_h = [], []
    print("Г1 — 🔑⁺ с разлоком доли казны (N ≥ 0,5%) против N = 0; шорт T − 7 → T + 1 сут, стоп 50%\n")
    for per in C.PER:
        x = X[X.per == per]
        e, c, mid = x[x.ev], x[x.ctl], x[~x.ev & ~x.ctl]
        z = x[x.ev | x.ctl]
        d, se = C.diff(z.net, z.ev, z.t); dh, seh = C.diff(z.hed, z.ev, z.t)
        parts.append((d, se, len(e))); parts_h.append((dh, seh, len(e)))
        print(f"{per}:")
        print(f"  с казной   {C.line(e, per)}")
        print(f"  без казны  {C.line(c, per)}")
        print(f"  0 < N < 0,5% {C.line(mid, per)}")
        print(f"  Δ = {d:+.2%} (t {d / se:+.1f}); с хеджем Δ = {dh:+.2%} (t {dh / seh:+.1f})")
    m, t = C.combine(parts); mh, th = C.combine(parts_h)
    print(f"\nвместе: Δ = {m:+.2%} (t {t:+.1f}); с хеджем Δ = {mh:+.2%} (t {th:+.1f})")
    print("\nРазрезы (Δ к контролю N = 0, по периодам):")
    sl = {"N 0,5–1%": (X.N >= 0.005) & (X.N < 0.01), "N 1–5%": (X.N >= 0.01) & (X.N < 0.05), "N ≥ 5%": X.N >= 0.05,
          "доля казны N/(U+N) ≥ 0,5": X.ev & (X.N / (X.share + X.N) >= 0.5),
          "доля казны < 0,5": X.ev & (X.N / (X.share + X.N) < 0.5),
          "ежемесячный график (≥ 6 за 365 сут)": X.ev & (X.joint >= 6), "прочие": X.ev & (X.joint < 6),
          "есть Foundation/Treasury ≥ 0,5%": X.ev & (X.Nft >= 0.005), "только прочие метки": X.ev & (X.Nft < 0.005)}
    for lab, msk in sl.items():
        out = []
        for per in C.PER:
            x = X[X.per == per]; s = msk[X.per == per]
            z = x[s | x.ctl]
            d, se = C.diff(z.net, s[z.index], z.t)
            out.append(f"n={int(s.sum()):3d} {x[s].net.mean():+.2%} Δ {d:+.2%} (t {d / se:+.1f})" if s.sum() >= 5 else
                       f"n={int(s.sum()):3d}")
        print(f"  {lab:38s} " + " | ".join(out))
    print("\nПроекты с наибольшим числом событий (N ≥ 0,5%):",
          X[X.ev].groupby("slug").size().sort_values(ascending=False).head(10).to_dict())


if __name__ == "__main__":
    report(build() if not (len(sys.argv) > 1 and sys.argv[1] == "report") else pd.read_pickle(f"{OUT}/s182_g1.pkl"))
