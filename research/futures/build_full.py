"""Сигналы по логике бота на фьючерсах Binance (архив data.binance.vision) → signals.pkl.
Отбор: серия ≥4 ч (разрывы ≤30 мин), движение за 4 ч = живая цена / close 15-мин свечи 16 назад (как в scanner.price_and_change).
Живая цена и вход — open минутной свечи, следующей за минутой поста. Правило 1: +8..+17%, правило 2: −17..−8% и B/R ≥ 5.
Кулдаун 24 ч по монете. Для каждого сигнала — минутные свечи цены и марк-цены на 73 ч вперёд и фандинг."""
import json, re, bisect, datetime, pickle, ast, os
import numpy as np, pandas as pd
from concurrent.futures import ThreadPoolExecutor
import bv
UTC = datetime.timezone.utc
T0 = datetime.datetime(2025, 2, 23, tzinfo=UTC).timestamp(); T1 = datetime.datetime(2026, 9, 28, tzinfo=UTC).timestamp()
MONTHS = [f"2025-{m:02d}" for m in range(1, 13)] + [f"2026-{m:02d}" for m in range(1, 10)]
GAP = 1800
# функции структуры — прямо из кода бота
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../bot/scanner.py")).read(); mod = ast.parse(src); ns = {}
for n in mod.body:
    if isinstance(n, ast.FunctionDef) and n.name in ("_zigzag", "_structure"): exec(ast.get_source_segment(src, n), ns)
_structure = ns["_structure"]

rows = []
POSTS = {}
for fn in ("posts_old.jsonl", "posts.jsonl", "posts_new.jsonl"):
    for ln in open(fn):
        p = json.loads(ln); POSTS[p[0]] = p
for pid, ts, txt in POSTS.values():
    ep = int(datetime.datetime.fromisoformat(ts).timestamp())
    for s in txt.splitlines():
        m = re.match(r'^([A-Z0-9]+)\s+([\d.]+[KMB]?)\s+([\d.]+[KMB]?)\s+([\d.]+)(?:\s+(-?[\d.]+))?\s*$', s.strip())   # 4 колонки (до осени 2025) или 5 (с CHNG)
        if m: rows.append((m.group(1), ep, float(m.group(4))))
df = pd.DataFrame(rows, columns=["sym", "epoch", "br"]).drop_duplicates().sort_values(["sym", "epoch"])
df["gap"] = df.groupby("sym").epoch.diff(); df["run_id"] = ((df.gap.isna()) | (df.gap > GAP)).groupby(df.sym).cumsum()
df["run_h"] = (df.epoch - df.groupby(["sym", "run_id"]).epoch.transform("min")) / 3600
cand = df[(df.run_h >= 4) & (df.epoch >= T0) & (df.epoch < T1)]
print("строк в постах", len(df), "| кандидатов (серия ≥4ч)", len(cand), "| монет", cand.sym.nunique(), flush=True)

with ThreadPoolExecutor(16) as ex:
    K15 = dict(zip(cand.sym.unique(), ex.map(lambda s: bv.klines(s, "klines", "15m", MONTHS), cand.sym.unique())))
nof = sorted(s for s, k in K15.items() if k is None); K15 = {s: k for s, k in K15.items() if k is not None}
print("нет на фьючерсах Binance:", len(nof), nof[:40], flush=True)

day = lambda t: datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d")
def m1(sym, kind, t_from, t_to):
    days = sorted({day(t) for t in range(int(t_from), int(t_to) + 86400, 86400) if t <= t_to} | {day(t_to)})
    return bv.klines(sym, kind, "1m", (), days)
# предварительно: может ли живая цена в пределах 15-мин свечи попасть в полосу
pre = []
for r in cand.itertuples():
    if r.sym not in K15: continue
    t, o, h, l, c = K15[r.sym].T; i = bisect.bisect_right(t, r.epoch) - 1
    if i < 97 or t[i] + 900 <= r.epoch: continue
    lo, hi = (l[i] / c[i - 16] - 1) * 100, (h[i] / c[i - 16] - 1) * 100
    if hi >= 8 and lo <= 17 or (lo <= -8 and hi >= -17 and r.br >= 5): pre.append(r)
print("предварительных", len(pre), flush=True)
need = sorted({(r.sym, day(r.epoch)) for r in pre})
with ThreadPoolExecutor(16) as ex:
    M1 = dict(zip(need, ex.map(lambda sd: bv.klines(sd[0], "klines", "1m", (), [sd[1]]), need)))
sig = []; last = {}
for r in pre:
    a = M1.get((r.sym, day(r.epoch)))
    if a is None: continue
    te = (r.epoch // 60 + 1) * 60; k = np.searchsorted(a[:, 0], te)
    if k >= len(a) or a[k, 0] != te: continue
    p = a[k, 1]
    t, o, h, l, c = K15[r.sym].T; i = bisect.bisect_right(t, r.epoch) - 1
    b4h = (p / c[i - 16] - 1) * 100
    rule = "1" if 8 <= b4h <= 17 else ("2" if -17 <= b4h <= -8 and r.br >= 5 else None)
    if not rule: continue
    if r.sym in last and r.epoch - last[r.sym] < 86400: continue
    last[r.sym] = r.epoch
    C = list(c[i - 96:i]) + [p]; H = list(h[i - 96:i + 1]); L = list(l[i - 96:i + 1])
    sig.append(dict(sym=r.sym, ep=int(r.epoch), te=te, rule=rule, br=r.br, b4h=b4h, entry=p,
                    from_peak=(p / max(h[i - 16:i]) - 1) * 100, from_low=(p / min(l[i - 16:i]) - 1) * 100,
                    rise_before=(c[i - 16] / c[i - 96] - 1) * 100, s_pump=_structure(C, H, L), s_dump=_structure(C, H, L, invert=True)))
print("сигналов", len(sig), "| правило 1", sum(s["rule"] == "1" for s in sig), "| правило 2", sum(s["rule"] == "2" for s in sig), flush=True)

def load(s):
    a = m1(s["sym"], "klines", s["te"], s["te"] + 73 * 3600); m = m1(s["sym"], "markPriceKlines", s["te"], s["te"] + 73 * 3600)
    return a, m
with ThreadPoolExecutor(16) as ex:
    data = list(ex.map(load, sig))
FUND = {}
for s, (a, m) in zip(sig, data):
    sel = (a[:, 0] >= s["te"]) & (a[:, 0] < s["te"] + 73 * 3600)
    s["t"], s["h"], s["l"], s["c"] = a[sel, 0].astype(int), a[sel, 2], a[sel, 3], a[sel, 4]
    mm = dict(zip(m[:, 0].astype(int), m[:, 2])) if m is not None else {}
    s["mh"] = np.array([mm.get(int(x), hh) for x, hh in zip(s["t"], s["h"])])   # нет марк-свечи — берём цену
    s["mark_ok"] = m is not None
    if s["sym"] not in FUND: FUND[s["sym"]] = bv.funding(s["sym"], MONTHS)
pickle.dump({"sig": sig, "fund": FUND, "nof": nof}, open("signals_full.pkl", "wb"))
print("готово; без марк-цены", sum(not s["mark_ok"] for s in sig))
