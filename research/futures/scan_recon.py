"""Сигналы точно по логике бота: проверка на каждом опросе, а не только в моменты постов.
Бот (scanner.scan): монета — кандидат, если была в посте за последние 30 мин и её серия (разрывы ≤ 30 мин) началась ≥ 4 ч назад;
рост за 4 ч = текущая цена / close 15-мин свечи на 16 свечей раньше текущей; правило 1: +8..+17%, правило 2: −17..−8% и B/R ≥ 5;
повтор по монете не раньше 24 ч. Опрос: до 04.10 12:10 — раз в 5 мин, потом раз в минуту."""
import json, re, datetime, pickle, bisect
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import bv
UTC = datetime.timezone.utc
ts = lambda *a: int(datetime.datetime(*a, tzinfo=UTC).timestamp())
T0, T1, SWITCH = ts(2026, 9, 29, 15, 28), ts(2026, 10, 16), ts(2026, 10, 4, 12, 10)
GAP, MIN_RUN = 1800, 4 * 3600
DAYS = ["2026-09-%02d" % d for d in range(28, 31)] + ["2026-10-%02d" % d for d in range(1, 16)]
day = lambda t: datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d")
rx = re.compile(r'^([A-Z0-9]+)\s+([\d.]+[KMB]?)\s+([\d.]+[KMB]?)\s+([\d.]+)\s+(-?[\d.]+)\s*$')
POSTS = {}
for fn in ("posts.jsonl", "posts_new.jsonl", "posts_oct.jsonl"):
    for ln in open(fn):
        p = json.loads(ln); POSTS[p[0]] = p
PT, BR = {}, {}
for pid, tstr, txt in sorted(POSTS.values(), key=lambda p: p[1]):
    ep = int(datetime.datetime.fromisoformat(tstr).timestamp())
    if ep < T0 - 8 * 3600 or ep > T1: continue
    for s in txt.splitlines():
        m = rx.match(s.strip())
        if m: PT.setdefault(m.group(1), []).append(ep); BR.setdefault(m.group(1), []).append(float(m.group(4)))
START = {}
for s, tl in PT.items():
    st = []; cur = tl[0]
    for k, t in enumerate(tl):
        if k and t - tl[k - 1] > GAP: cur = t
        st.append(cur)
    START[s] = st
grid = list(range(T0, SWITCH, 300)) + list(range(SWITCH, T1, 60))
cand = {}
for s, tl in PT.items():
    for T in grid:
        j = bisect.bisect_right(tl, T) - 1
        if j >= 0 and T - tl[j] <= GAP and T - START[s][j] >= MIN_RUN:
            cand.setdefault(s, []).append((T, BR[s][j]))
print("монет-кандидатов", len(cand), "| моментов", sum(map(len, cand.values())), flush=True)
with ThreadPoolExecutor(16) as ex:
    K15 = dict(zip(cand, ex.map(lambda s: bv.klines(s, "klines", "15m", ["2026-09"], DAYS[3:]), cand)))
K15 = {s: k for s, k in K15.items() if k is not None}
pre = []
for s, lst in cand.items():
    if s not in K15: continue
    t, o, h, l, c = K15[s].T
    for T, br in lst:
        i = bisect.bisect_right(t, T) - 1
        if i < 16 or t[i] + 900 <= T: continue
        lo, hi = (l[i] / c[i - 16] - 1) * 100, (h[i] / c[i - 16] - 1) * 100
        if (hi >= 8 and lo <= 17) or (lo <= -8 and hi >= -17 and br >= 5): pre.append((T, s, br, c[i - 16]))
need = sorted({(s, day(T)) for T, s, br, c17 in pre})
print("предварительных моментов", len(pre), "| дней минуток", len(need), flush=True)
with ThreadPoolExecutor(16) as ex:
    M1 = dict(zip(need, ex.map(lambda sd: bv.klines(sd[0], "klines", "1m", (), [sd[1]]), need)))
sig, last = [], {}
for T, s, br, c17 in sorted(pre):
    a = M1.get((s, day(T)))
    if a is None: continue
    k = np.searchsorted(a[:, 0], T // 60 * 60)
    if k >= len(a) or a[k, 0] != T // 60 * 60: continue
    p = a[k, 1]; b4h = (p / c17 - 1) * 100
    rule = "pump" if 8 <= b4h <= 17 else ("dump" if -17 <= b4h <= -8 and br >= 5 else None)
    if not rule or (s in last and T - last[s] < 86400): continue
    last[s] = T; sig.append(dict(sym=s, ep=T, rule=rule, br=br, b4h=b4h, entry=p))
pickle.dump(sig, open("signals_scan.pkl", "wb"))
print("сигналов", len(sig))
