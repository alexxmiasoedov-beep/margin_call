"""s228 — расчёт по записи до расчёта (ВЫВОДЫ.md): 23 правила 🗳 без займа и канала на наблюдениях вне канала и в канале.
Честные сделки (одна на монету до выхода) отдельно для «вне канала» и «в канале»; доход — шорт 4 ч с хеджем индексом альтов;
t по неделям; плацебо — 20 случайных отметок той же монеты в том же календарном месяце.
Запуск из /home/user/mc_data после features.py full: python3 <repo>/research/s228/evaluate.py"""
import os
import sys
import tempfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s223"))
os.environ.setdefault("STATE_FILE", os.path.join(tempfile.mkdtemp(), "state.json"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "bot"))
from committee import ct, honest  # noqa: E402
import scanner  # noqa: E402

DAY = 86400
TS = lambda d: int(pd.Timestamp(d, tz="UTC").timestamp())  # noqa: E731
SEG = [("до A", TS("2024-10-01"), TS("2025-02-20")), ("A", TS("2025-02-20"), TS("2025-10-01")),
       ("B", TS("2025-10-01"), TS("2026-04-01")), ("C", TS("2026-04-01"), TS("2026-10-22")),
       ("D", TS("2026-10-22"), TS("2026-11-20")), ("C + D", TS("2026-04-01"), TS("2026-11-20"))]
MID = TS("2026-07-26")
EXC = {"bor", "rep", "net", "rb", "b4", "r4x", "b24", "r24x", "net7", "place", "pres7", "run", "hold", "bqv", "rate", "ux",
       "dr24", "lim", "bmc", "wave", "zbor", "zrep", "znet", "zrate"}
RULES = [r for r in scanner.C4_RULES if not any(f in EXC for f, _, _ in r)]
CORE = (0.022122454, 0.6309575267)
STRICT = (0.130121822, 0.6309575267)


def cond(D, f, op, q):
    x = D[f].to_numpy(float)
    with np.errstate(invalid="ignore"):
        return np.where(np.isfinite(x), x <= q if op == "le" else x >= q, False)


_POOL = {}


def placebo(D, tk, rng, draws=20):
    """Для каждой сделки — среднее исхода 20 случайных отметок той же монеты в том же месяце."""
    if not _POOL:
        mon = pd.to_datetime(D["T"], unit="s").dt.to_period("M").astype(str).to_numpy()
        key = D.s.astype(str).to_numpy() + "|" + mon
        _POOL["key"] = key
        _POOL["pools"] = {k: D.y.to_numpy(float)[ix] for k, ix in pd.Series(key).groupby(key).groups.items()}
    key, pools = _POOL["key"], _POOL["pools"]
    out = np.full(len(tk), np.nan)
    for j, i in enumerate(tk):
        p = pools.get(key[i])
        if p is not None and len(p) >= 5:
            out[j] = rng.choice(p, draws).mean()
    return out


def stats(D, tk, pl, lo, hi):
    T = D["T"].to_numpy(np.int64)[tk]; y = D.y.to_numpy(float)[tk]
    m = (T >= lo) & (T < hi)
    mon = (min(hi, TS("2026-11-20")) - lo) / (30.44 * DAY)
    mean, t, n = ct(y[m], T[m])
    dm, dt, _ = ct(y[m] - pl[m], T[m])
    return {"n": n, "в мес.": n / mon, "доход": mean, "t": t, "плацебо": np.nanmean(pl[m]) if n else np.nan,
            "сверх плацебо": dm, "t сверх": dt, "h1": np.nanmean(y[m & (T < MID)]) if (m & (T < MID)).any() else np.nan,
            "h2": np.nanmean(y[m & (T >= MID)]) if (m & (T >= MID)).any() else np.nan}


def main():
    D = pd.read_pickle("s228/feat.pkl").sort_values(["T", "s"]).reset_index(drop=True)
    y = D.y.to_numpy(float); end = D.u_e.to_numpy(float)
    votes = np.zeros(len(D), np.int32)
    for r in RULES:
        votes += np.logical_and.reduce([cond(D, f, op, q) for f, op, q in r])
    core = cond(D, "dlsr24", "ge", CORE[0]) & cond(D, "zoi4", "ge", CORE[1])
    strict = cond(D, "dlsr24", "ge", STRICT[0]) & cond(D, "zoi4", "ge", STRICT[1])
    inch = D.inch.to_numpy(bool)
    print(f"наблюдений {len(D)} (в канале {inch.sum()}), монет {D.s.nunique()}, правил без займа и канала {len(RULES)}")
    sels = {"k ≥ 3": votes >= 3, "k ≥ 2": votes >= 2, "k ≥ 1": votes >= 1, "ядро": core, "строгое ядро": strict,
            "все наблюдения": np.ones(len(D), bool)}
    rng = np.random.default_rng(228)
    rows = []
    keep = {}
    for grp, gm in (("вне канала", ~inch), ("в канале", inch)):
        for name, sel in sels.items():
            tk = honest(sel & gm, D, y, end)
            pl = placebo(D, tk, rng) if name != "все наблюдения" else np.full(len(tk), np.nan)
            keep[(grp, name)] = (tk, pl)
            for seg, lo, hi in SEG:
                r = stats(D, tk, pl, lo, hi)
                rows.append({"группа": grp, "отбор": name, "отрезок": seg, **r})
    R = pd.DataFrame(rows)
    R.to_pickle("s228/evaluate.pkl")
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
    show = R.copy()
    for c in ("доход", "плацебо", "сверх плацебо", "h1", "h2"):
        show[c] = (show[c] * 100).map(lambda v: f"{v:+.2f}%" if np.isfinite(v) else "—")
    for c in ("t", "t сверх"):
        show[c] = show[c].map(lambda v: f"{v:+.1f}" if np.isfinite(v) else "—")
    show["в мес."] = show["в мес."].map(lambda v: f"{v:.1f}")
    print(show.drop(columns=["h1", "h2"]).to_string(index=False))
    # порог: вне канала, k ≥ 3, C + D
    r = R[(R["группа"] == "вне канала") & (R["отбор"] == "k ≥ 3") & (R["отрезок"] == "C + D")].iloc[0]
    ok = [("доход > 0", r["доход"] > 0), ("t ≥ 3", r["t"] >= 3), ("≥ 20 в мес.", r["в мес."] >= 20),
          ("половины > 0", r["h1"] > 0 and r["h2"] > 0), ("сверх плацебо > 0", r["сверх плацебо"] > 0)]
    print(f"\nПОРОГ (вне канала, k ≥ 3, C + D): {r['n']} сделок ({r['в мес.']:.1f} в мес.), {r['доход']:+.2%} (t {r['t']:+.1f}), "
          f"половины {r['h1']:+.2%} / {r['h2']:+.2%}, сверх плацебо {r['сверх плацебо']:+.2%} (t {r['t сверх']:+.1f})")
    print("  " + "; ".join(f"{a} — {'да' if c else 'нет'}" for a, c in ok) + ("  → ПРОЙДЕН" if all(c for _, c in ok) else "  → не пройден"))
    # что держит k ≥ 3: со строгим ядром и без
    tk, _ = keep[("вне канала", "k ≥ 3")]
    T = D["T"].to_numpy(np.int64)
    for seg, lo, hi in SEG:
        m = (T[tk] >= lo) & (T[tk] < hi)
        a = tk[m & strict[tk]]; b = tk[m & ~strict[tk]]
        ma, ta, na = ct(y[a], T[a]); mb, tb, nb = ct(y[b], T[b])
        print(f"  {seg:6s} k ≥ 3 вне канала: со строгим ядром {na} сделок {ma:+.2%} (t {ta:+.1f}); "
              f"без него {nb} {mb:+.2%} (t {tb:+.1f})")
    # по месяцам C + D
    m = (T[tk] >= SEG[3][1])
    mon = pd.to_datetime(T[tk][m], unit="s").to_period("M")
    print("\n  вне канала, k ≥ 3, по месяцам C + D:")
    for p, ix in pd.Series(np.arange(m.sum())).groupby(mon).groups.items():
        yy = y[tk][m][ix]
        print(f"    {p}: {len(yy)} сделок, {np.mean(yy):+.2%}")


if __name__ == "__main__":
    main()
