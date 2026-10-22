"""Влияние знака «+» в CHNG на правила 1 и 2: доля моментов «монета в канале ≥ 4 ч», которые бот теряет из-за неразобранных строк."""
import sys, json, datetime, re, os
from collections import defaultdict
import numpy as np
sys.path.insert(0, os.environ.get("BOT_DIR", "bot"))   # папка bot репозитория: BOT_DIR=…/margin_call/bot
os.environ.setdefault("STATE_FILE", "/tmp/rp_fid_state.json")
import scanner
FIX = re.compile(scanner.ROW.pattern.replace(r"(-?[\d.]+)\s*$", r"([+-]?[\d.]+)\s*$"))
assert FIX.pattern != scanner.ROW.pattern
raw = {}
for fn in ("posts_new.jsonl", "posts_oct.jsonl", "posts_oct2.jsonl", "posts.jsonl"):
    for ln in open(fn):
        x = json.loads(ln)
        if len(x) >= 3 and isinstance(x[2], str) and "B/R" in x[2][:80]: raw[x[0]] = (datetime.datetime.fromisoformat(x[1]).timestamp(), x[2])
P = sorted(raw.values())
def series(rx):
    S = defaultdict(list)
    for ts, txt in P:
        for l in txt.splitlines():
            r = rx.match(l.strip())
            if r: S[r.group(1)].append(ts)
    return S
A, B = series(scanner.ROW), series(FIX)
def long_points(tt):
    tt = np.array(tt); st = np.r_[0, np.flatnonzero(np.diff(tt) > 30 * 60) + 1]; start = np.zeros(len(tt))
    for a, b in zip(st, np.r_[st[1:], len(tt)]): start[a:b] = tt[a]
    return set(tt[(tt - start) >= 4 * 3600].round())
lost = defaultdict(lambda: [0, 0]); coins_hit = defaultdict(set)
for s in B:
    pb = long_points(B[s]); pa = long_points(A.get(s, [])) if s in A else set()
    for t in pb:
        m = datetime.datetime.utcfromtimestamp(t).strftime("%Y-%m"); lost[m][0] += 1
        if t not in pa: lost[m][1] += 1; coins_hit[m].add(s)
print("месяц    моментов ≥4 ч (с «+»)  бот не видит  монет задето")
for m in sorted(lost):
    if m >= "2025-09": print(f"{m}  {lost[m][0]:9d}  {lost[m][1] / lost[m][0]:10.1%}  {len(coins_hit[m]):6d}")
