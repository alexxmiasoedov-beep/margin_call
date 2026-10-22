"""Сверка выбора 🏦 в боте (scanner.bf_pick) с бэктестом (journal_sim2.py) на исторических постах и свечах: каждый 9-й день.
Запуск из папки с данными исследования (s2/k2y.pkl, s7/margin.pkl, s10/daily_panel.pkl); BOT_DIR — папка бота."""
import os, sys, pickle, re, datetime
import numpy as np, pandas as pd
os.environ.setdefault("STATE_FILE", "/tmp/bf_parity_state.json")
sys.path.insert(0, os.environ.get("BOT_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bot")))
import scanner
K = pickle.load(open("s2/k2y.pkl", "rb")); FU = pickle.load(open("s2/fund2y.pkl", "rb"))
m = pickle.load(open("s7/margin.pkl", "rb")); G = m["G"]
chan = {c: np.unique(a[:, 0]) for c, a in G.items()}
D = pd.read_pickle("s10/daily_panel.pkl")
d = D[(D.v >= 10e6) & D.ret7.notna()]
pool = d[(d.sh7 > 0) & ~(d.f0 < -0.001)]
top = pool.assign(rr=pool.groupby("T").sh7.rank(ascending=False, method="first")).query("rr <= 10")
bt = top.assign(vr=top.groupby("T").vol.rank(ascending=False, method="first")).query("vr <= 5")
bt_sets = bt.groupby("T").s.apply(set); bt_top = top.groupby("T").s.apply(set)
def fut(c):
    for p in ("", "1000", "10000", "100000", "1000000"):
        if p + c in K: return (p + c, int(K[p + c]["t"][0]))
    return None
days = sorted(bt_sets.index)[::9]
agree_keep = agree_top = 0; diffs = []
for T in days:
    day0 = T - 3600; lo = day0 - 7 * 86400
    cnt = {c: int(np.searchsorted(tt, day0) - np.searchsorted(tt, lo)) for c, tt in chan.items()}
    cnt = {c: n for c, n in cnt.items() if n > 0}
    def kl(fs):
        a = K[fs]; j = int(np.searchsorted(a["t"], T))
        lo_ = max(0, j - 673)
        return [[int(a["t"][i]) * 1000, 0, 0, 0, float(a["c"][i]), 0, 0, float(a["qv"][i])] for i in range(lo_, j)]
    def fund(fs):
        f = FU.get(fs)
        if f is None: return None
        k = np.searchsorted(f[:, 0], T - 3600, "right") - 1
        return float(f[k, 2] / f[k, 1]) if k >= 0 else None
    tp, keep, miss = scanner.bf_pick(cnt, T, fut, kl, fund)
    a, b = {x[1] for x in keep}, bt_sets[T]
    at, btt = {x[1] for x in tp}, bt_top[T]
    agree_keep += a == b; agree_top += at == btt
    if a != b: diffs.append((datetime.datetime.utcfromtimestamp(T).strftime("%d.%m.%Y"), sorted(a - b), sorted(b - a), sorted(at ^ btt)))
print(f"дней проверено {len(days)}: совпал топ-10 — {agree_top}, совпали 5 выбранных — {agree_keep}")
for x in diffs[:12]: print("   ", x[0], "только бот:", x[1], "только бэктест:", x[2], "| разница в топ-10:", x[3])
