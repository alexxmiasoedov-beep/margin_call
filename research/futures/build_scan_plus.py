"""Вариант с исправленным разбором строк (CHNG со знаком «+»). Сигналы за всю историю канала (23.02.2025–15.10.2026) точно по логике бота (scanner.scan) → signals_scan_plus.pkl.
Проверка на каждом опросе раз в минуту: монета — кандидат, если была в посте за последние 30 мин и её серия (разрывы ≤ 30 мин)
началась ≥ 4 ч назад; рост за 4 ч = цена в начале минуты / close 15-мин свечи на 16 свечей раньше текущей;
правило 1: +8..+17%, правило 2: −17..−8% и B/R ≥ 5; повтор по монете не раньше 24 ч.
Вход — open этой минуты (бот входит в секунды после опроса). Для каждого сигнала — минутные свечи цены и марк-цены на 73 ч
и фандинг (октябрь 2026 — оценка по индексу премии, fund_est.py)."""
import json, re, datetime, pickle, ast, sys
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import bv
from fund_est import estimate
UTC = datetime.timezone.utc
ts = lambda *a: int(datetime.datetime(*a, tzinfo=UTC).timestamp())
T0, T1 = ts(2025, 2, 23), ts(2026, 10, 15, 23)
MONTHS = [f"2025-{m:02d}" for m in range(1, 13)] + [f"2026-{m:02d}" for m in range(1, 10)]
ODAYS = [f"2026-10-{d:02d}" for d in range(1, 17)]
GAP, MIN_RUN = 1800, 4 * 3600
day = lambda t: datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d")
log = lambda *a: print(datetime.datetime.now().strftime("%H:%M:%S"), *a, flush=True)
src = open("/home/user/margin_call/bot/scanner.py").read(); mod = ast.parse(src); ns = {}
for n in mod.body:
    if isinstance(n, ast.FunctionDef) and n.name in ("_zigzag", "_structure"): exec(ast.get_source_segment(src, n), ns)
_structure = ns["_structure"]
rx = re.compile(r'^([A-Z0-9]+)\s+([\d.]+[KMB]?)\s+([\d.]+[KMB]?)\s+([\d.]+)(?:\s+([+-]?[\d.]+))?\s*$')   # CHNG со знаком «+» — как в исправленном боте
POSTS = {}
for fn in ("posts_old.jsonl", "posts.jsonl", "posts_new.jsonl", "posts_oct.jsonl"):
    for ln in open(fn):
        p = json.loads(ln); POSTS[p[0]] = (int(datetime.datetime.fromisoformat(p[1]).timestamp()), p[2])
PT, BR = {}, {}
for ep, txt in sorted(POSTS.values()):
    if ep < T0 - 8 * 3600 or ep >= T1: continue
    seen = set()
    for s in txt.splitlines():
        m = rx.match(s.strip())
        if m and m.group(1) not in seen:
            seen.add(m.group(1)); PT.setdefault(m.group(1), []).append(ep); BR.setdefault(m.group(1), []).append(float(m.group(4)))
log("постов", len(POSTS), "| монет", len(PT))
def cand_minutes(s):
    tl = PT[s]; br = BR[s]; Ts, Bs = [], []; cur = tl[0]
    for k, t in enumerate(tl):
        if k and t - tl[k - 1] > GAP: cur = t
        a = max(t, cur + MIN_RUN, T0); b = min(tl[k + 1] if k + 1 < len(tl) else t + GAP + 1, t + GAP + 1, T1)
        a = (a + 59) // 60 * 60
        if a < b: x = np.arange(a, b, 60); Ts.append(x); Bs.append(np.full(len(x), br[k]))
    return (np.concatenate(Ts), np.concatenate(Bs)) if Ts else (None, None)
CM = {s: cand_minutes(s) for s in PT}; CM = {s: v for s, v in CM.items() if v[0] is not None}
log("монет с кандидатами", len(CM), "| минут-кандидатов", sum(len(v[0]) for v in CM.values()))
with ThreadPoolExecutor(16) as ex:
    K15 = dict(zip(CM, ex.map(lambda s: bv.klines(s, "klines", "15m", MONTHS, ODAYS), CM)))
nof = sorted(s for s, k in K15.items() if k is None); K15 = {s: k for s, k in K15.items() if k is not None}
log("нет на фьючерсах Binance:", len(nof))
pre = {}
for s, (T, B) in CM.items():
    if s not in K15: continue
    t15, h15, l15, c15 = K15[s][:, 0], K15[s][:, 2], K15[s][:, 3], K15[s][:, 4]
    i = np.searchsorted(t15, T, side="right") - 1
    ok = (i >= 16) & (t15[np.maximum(i, 0)] + 900 > T); i = np.where(ok, i, 16)
    c17 = c15[i - 16]; lo = l15[i] / c17 - 1; hi = h15[i] / c17 - 1
    band = ok & (((hi >= 0.08) & (lo <= 0.17)) | ((lo <= -0.08) & (hi >= -0.17) & (B >= 5)))
    if band.any(): pre[s] = (T[band], B[band], c17[band], i[band])
need = sorted({(s, day(t)) for s, v in pre.items() for t in v[0]})
log("минут после фильтра по 15-мин свечам", sum(len(v[0]) for v in pre.values()), "| дней минуток", len(need))
with ThreadPoolExecutor(16) as ex:
    M1 = dict(zip(need, ex.map(lambda sd: bv.klines(sd[0], "klines", "1m", (), [sd[1]]), need)))
log("минутки загружены; пустых", sum(v is None for v in M1.values()))
sig = []
for s, (T, B, C17, I) in pre.items():
    last = -1e18; t15, h15, l15, c15 = K15[s][:, 0], K15[s][:, 2], K15[s][:, 3], K15[s][:, 4]
    for T_, br, c17, i in zip(T, B, C17, I):
        if T_ - last < 86400: continue
        a = M1.get((s, day(T_)))
        if a is None: continue
        k = np.searchsorted(a[:, 0], T_)
        if k >= len(a) or a[k, 0] != T_: continue
        p = a[k, 1]; b4h = (p / c17 - 1) * 100
        rule = "1" if 8 <= b4h <= 17 else ("2" if -17 <= b4h <= -8 and br >= 5 else None)
        if not rule: continue
        last = T_
        C = list(c15[max(i - 96, 0):i]) + [p]; H = list(h15[max(i - 96, 0):i + 1]); L = list(l15[max(i - 96, 0):i + 1])
        sig.append(dict(sym=s, ep=int(T_), te=int(T_), rule=rule, br=br, b4h=b4h, entry=p,
                        from_peak=(p / max(h15[i - 16:i]) - 1) * 100, from_low=(p / min(l15[i - 16:i]) - 1) * 100,
                        rise_before=(c15[i - 16] / c15[i - 96] - 1) * 100 if i >= 96 else None,
                        s_pump=_structure(C, H, L) if i >= 96 else None, s_dump=_structure(C, H, L, invert=True) if i >= 96 else None))
sig.sort(key=lambda s: s["ep"])
log("сигналов", len(sig), "| правило 1", sum(s["rule"] == "1" for s in sig), "| правило 2", sum(s["rule"] == "2" for s in sig))
def m1(sym, kind, t_from, t_to):
    days = sorted({day(t) for t in range(int(t_from), int(t_to) + 86400, 86400) if t <= t_to} | {day(t_to)})
    days = [d for d in days if d <= "2026-10-15"]
    return bv.klines(sym, kind, "1m", (), days)
def load(s):
    return m1(s["sym"], "klines", s["te"], s["te"] + 73 * 3600), m1(s["sym"], "markPriceKlines", s["te"], s["te"] + 73 * 3600)
with ThreadPoolExecutor(16) as ex:
    data = list(ex.map(load, sig))
log("пути после входа загружены")
END = ts(2026, 10, 16)
FUND = {}
def fund(sym):
    rows = []
    for m in MONTHS:
        for p in bv.rows(bv.fetch(f"monthly/fundingRate/{sym}USDT/{sym}USDT-fundingRate-{m}.zip")):
            try: rows.append((int(p[0]) // 1000, int(float(p[1])), float(p[2])))
            except (ValueError, IndexError): pass
    rows.sort(); out = [(t, r) for t, iv, r in rows]
    if rows and rows[-1][0] > ts(2026, 9, 20):              # октябрь — оценка по индексу премии
        orig = next((iv for t, iv, r in reversed(rows) if iv in (4, 8)), 8)
        out += estimate(sym, rows[-1][0], rows[-1][1], END, orig)
    return np.array(out) if out else None
syms = sorted({s["sym"] for s in sig})
with ThreadPoolExecutor(8) as ex:
    FUND = dict(zip(syms, ex.map(fund, syms)))
out = []
for s, (a, m) in zip(sig, data):
    if a is None: continue
    sel = (a[:, 0] >= s["te"]) & (a[:, 0] < s["te"] + 73 * 3600)
    s["t"], s["h"], s["l"], s["c"] = a[sel, 0].astype(int), a[sel, 2], a[sel, 3], a[sel, 4]
    mm = dict(zip(m[:, 0].astype(int), m[:, 2])) if m is not None else {}
    s["mh"] = np.array([mm.get(int(x), hh) for x, hh in zip(s["t"], s["h"])])
    s["mark_ok"] = m is not None
    out.append(s)
pickle.dump({"sig": out, "fund": FUND, "nof": nof}, open("signals_scan_plus.pkl", "wb"))
log("готово:", len(out), "сигналов; без марк-цены", sum(not s["mark_ok"] for s in out))
