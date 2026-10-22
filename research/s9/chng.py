"""CHNG маржинального бота (с 02.09.2025): «> 1 — сильный приток маржи; смена с + на − — возврат (закрытие)».
По логике автора: после роста цены CHNG > 1 → шорт. События: первый пост, где CHNG монеты ≥ порога (после ≥ 24 ч без такого);
смена знака CHNG с ≥ +1 на ≤ −0,5 за ≤ 3 ч. Исходы как в md_events."""
import json, re, datetime
import numpy as np, pandas as pd
exec(open("s9/md_events.py").read().split("# 15-мин сетка постов канала")[0])
def num(x):
    x = x.strip().replace(",", ".")
    mm = {"K": 1e3, "M": 1e6, "B": 1e9}.get(x[-1:].upper(), 1)
    try: return float(x[:-1] if mm != 1 else x) * mm
    except ValueError: return np.nan
rows = []
for f in ("posts.jsonl", "posts_new.jsonl", "posts_oct.jsonl", "posts_oct2.jsonl", "posts_old.jsonl"):
    for ln in open(f):
        x = json.loads(ln)
        if len(x) < 3 or not isinstance(x[2], str) or "CHNG" not in x[2][:80]: continue
        T = datetime.datetime.fromisoformat(x[1]).timestamp()
        for l in x[2].split("\n")[2:]:
            p = l.split()
            if len(p) < 5 or l.startswith("MarginData"): continue
            try: ch = float(p[4])
            except ValueError: continue
            rows.append((re.sub(r"[^\w]", "", p[0]), T, num(p[1]), num(p[2]), ch))
C = pd.DataFrame(rows, columns=["c", "t", "bor", "rep", "chng"]).drop_duplicates(["c", "t"]).sort_values(["c", "t"])
print("строк с CHNG:", len(C), datetime.datetime.utcfromtimestamp(C.t.min()), "→", datetime.datetime.utcfromtimestamp(C.t.max()))
print("CHNG перцентили 1/10/50/90/99:", np.percentile(C.chng, [1, 10, 50, 90, 99]))
ev = []
for c0, g in C.groupby("c"):
    s = sym_of.get(c0) or sym_of.get(strip(c0))
    if s is None or s not in K: continue
    tt, ch = g.t.values, g.chng.values; last = -1e18
    for i in range(len(tt)):
        if ch[i] >= 1 and tt[i] - last >= 86400: ev.append((s, tt[i], "CH≥1", ch[i])); last = tt[i]
    for i in range(len(tt)):
        if ch[i] <= -0.5:
            k = np.flatnonzero((tt >= tt[i] - 3 * 3600) & (tt < tt[i]) & (ch >= 1))
            if len(k): ev.append((s, tt[i], "CH+→−", ch[i]))
E = pd.DataFrame(ev, columns=["s", "t", "ev", "ch"])
out = []
for x in E.itertuples():
    a = K[x.s]; j = int(np.searchsorted(a["t"], x.t, "right") - 1)
    if j < 300 or j >= len(a["t"]) - 2: continue
    o = outcomes(x.s, j); cx = ctx(x.s, j)
    if o is None or cx is None: continue
    out.append({**x._asdict(), **o, **{f"c_{k}": v for k, v in cx.items()}})
X = pd.DataFrame(out)
def dedup(g, h=24):
    g = g.sort_values("t"); keep = []; last = {}
    for i, s, t in zip(g.index, g.s, g.t):
        if t - last.get(s, -1e18) >= h * 3600: keep.append(i); last[s] = t
    return g.loc[keep]
for e in ("CH≥1", "CH+→−"):
    g0 = dedup(X[X.ev == e])
    for nm, m in (("все", g0.s == g0.s), ("за сутки ≥ +10% (после роста)", g0.c_r24 >= 0.10), ("за сутки ≥ +20%", g0.c_r24 >= 0.20),
                  ("за сутки в ±5%", g0.c_r24.abs() <= 0.05), ("за сутки ≤ −10%", g0.c_r24 <= -0.10)):
        g = g0[m]
        if len(g) < 15: continue
        print(f"{e:6s} {nm:32s} n={len(g):4d} r24 {g.r24.mean()*100:+.1f}% | " + " ".join(f"{c}: {g[c].mean()*100:+.2f} WR {(g[c] > 0).mean():.0%}" for c in ("S_10_25", "S_10_10", "L_10_10", "L_30_15")))
X.to_pickle("s9/chng_events.pkl")
MID = datetime.datetime(2026, 4, 1, tzinfo=datetime.timezone.utc).timestamp()
B = pd.read_pickle("s9/repay_base.pkl"); B = B[B.t >= C.t.min()]
def show(nm, g, cols):
    h1, h2 = g[g.t < MID], g[g.t >= MID]
    print(f"  {nm:44s} n={len(g):4d} ({len(h1)}/{len(h2)}) | " + " ".join(f"{c}: {g[c].mean()*100:+.2f} ({h1[c].mean()*100:+.2f}/{h2[c].mean()*100:+.2f}) WR {(g[c] > 0).mean():.0%}" for c in cols))
g0 = dedup(X[X.ev == "CH≥1"])
print("=== CH ≥ 1, половины: 09.2025–03.2026 / 04–10.2026")
for thr in (0.10, 0.15, 0.20):
    show(f"после роста ≥ {thr:.0%}: шорт", g0[g0.c_r24 >= thr], ("S_10_25", "S_10_10", "S_7_20"))
    show(f"  база: в канале ≥ 6 ч и рост ≥ {thr:.0%}", B[B.c_r24 >= thr], ("S_10_25", "S_10_10", "S_7_20"))
for thr in (-0.10, -0.15, -0.20):
    show(f"после падения ≤ {thr:.0%}: лонг", g0[g0.c_r24 <= thr], ("L_30_15", "L_20_10", "L_10_10"))
    show(f"  база: в канале ≥ 6 ч и падение ≤ {thr:.0%}", B[B.c_r24 <= thr], ("L_30_15", "L_20_10", "L_10_10"))
# пересечение с шортом после отдачи
R = pd.read_pickle("s9/repay_rule.pkl")
up = g0[g0.c_r24 >= 0.10]
ov = [((R.s == s) & ((R.t - t).abs() <= 24 * 3600)).any() for s, t in zip(up.s, up.t)]
print("CH≥1 после роста ≥ 10%, совпадают с шортом после отдачи (±24 ч):", sum(ov), "из", len(up))
